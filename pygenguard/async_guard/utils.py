"""
Async Utilities - Helper functions for async operations.
"""

import asyncio
from typing import Any, Awaitable, Callable, TypeVar, Union
from functools import wraps

T = TypeVar("T")


def run_sync(coro: Awaitable[T]) -> T:
    """
    Run an async coroutine synchronously.
    
    Handles the case where an event loop may already be running.
    
    Args:
        coro: The coroutine to run
    
    Returns:
        The result of the coroutine
    
    Usage:
        result = run_sync(async_guard.inspect(prompt, session))
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop is not None and loop.is_running():
        # Loop already running (e.g., in Jupyter notebook)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        # No loop running, create one
        return asyncio.run(coro)


async def maybe_await(value: Union[T, Awaitable[T]]) -> T:
    """
    Await a value if it's a coroutine, otherwise return it.
    
    Useful for handling both sync and async return values.
    
    Args:
        value: Either a direct value or an awaitable
    
    Returns:
        The resolved value
    
    Usage:
        result = await maybe_await(some_function())
    """
    if asyncio.iscoroutine(value) or asyncio.isfuture(value):
        return await value
    return value


def async_to_sync(func: Callable[..., Awaitable[T]]) -> Callable[..., T]:
    """
    Decorator to convert an async function to sync.
    
    Usage:
        @async_to_sync
        async def my_async_func():
            return await something()
        
        # Can now call synchronously
        result = my_async_func()
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        return run_sync(func(*args, **kwargs))
    return wrapper


def sync_to_async(func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    """
    Decorator to run a sync function in a thread pool.
    
    Prevents blocking the event loop.
    
    Usage:
        @sync_to_async
        def cpu_intensive_task():
            # Heavy computation
            return result
        
        # Can now await it
        result = await cpu_intensive_task()
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper


class AsyncBatcher:
    """
    Batches multiple async calls together for efficiency.
    
    Useful for reducing overhead when processing many requests.
    
    Usage:
        batcher = AsyncBatcher(guard.inspect, batch_size=10, timeout=0.1)
        
        # Queue requests
        result = await batcher.submit(prompt, session)
    """
    
    def __init__(
        self,
        func: Callable[..., Awaitable[T]],
        batch_size: int = 10,
        timeout: float = 0.1
    ):
        """
        Args:
            func: The async function to batch
            batch_size: Maximum batch size
            timeout: Max time to wait for batch to fill (seconds)
        """
        self.func = func
        self.batch_size = batch_size
        self.timeout = timeout
        
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task = None
        self._started = False
    
    async def start(self) -> None:
        """Start the batcher background task."""
        if not self._started:
            self._task = asyncio.create_task(self._processor())
            self._started = True
    
    async def stop(self) -> None:
        """Stop the batcher."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._started = False
    
    async def submit(self, *args, **kwargs) -> T:
        """
        Submit a request to be batched.
        
        Returns the result when processing completes.
        """
        if not self._started:
            await self.start()
        
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        await self._queue.put((args, kwargs, future))
        return await future
    
    async def _processor(self) -> None:
        """Background task that processes batched requests."""
        while True:
            batch = []
            deadline = asyncio.get_event_loop().time() + self.timeout
            
            # Collect items until batch full or timeout
            while len(batch) < self.batch_size:
                try:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        break
                    
                    item = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=remaining
                    )
                    batch.append(item)
                except asyncio.TimeoutError:
                    break
            
            if batch:
                # Process batch concurrently
                tasks = [
                    self.func(*args, **kwargs) 
                    for args, kwargs, _ in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Deliver results
                for (_, _, future), result in zip(batch, results):
                    if isinstance(result, Exception):
                        future.set_exception(result)
                    else:
                        future.set_result(result)
            else:
                # No items, yield control
                await asyncio.sleep(0.01)
