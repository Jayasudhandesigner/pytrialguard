# PyGenGuard

**Runtime security and governance framework for GenAI systems.**

PyGenGuard enforces trust, intent, cost, and compliance policies **before and after** model execution. It sits between your application and the LLM, acting as a deterministic security layer.

[![PyPI version](https://badge.fury.io/py/pygenguard.svg)](https://badge.fury.io/py/pygenguard)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)

---

## What's New in v0.2.0 🚀

- **Plugin System**: Create custom security planes with the `BasePlane` abstract class
- **Async Support**: `AsyncGuard` for high-concurrency applications (FastAPI, aiohttp)
- **Redis Adapters**: Distributed session storage for multi-instance deployments

---

## What problem does this solve?

GenAI systems face unique security challenges:

- **Prompt injection**: Users bypassing system instructions
- **Privilege escalation**: "Ignore previous instructions" attacks
- **Session hijacking**: Attackers taking over authenticated sessions
- **Denial-of-wallet**: Token flooding to drain API budgets
- **Compliance violations**: PII leakage, unaudited decisions

PyGenGuard blocks these threats with **deterministic, offline-capable** checks.

---

## Where does it sit in my system?

```
┌─────────────────────────────────────────────────────────────────┐
│                         Your Application                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PyGenGuard.inspect()                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ Identity │→│  Intent  │→│ Context  │→│Economics │→│Comply  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│                     ↑ Custom Plugins ↑                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              ┌─────────┐         ┌─────────┐
              │  ALLOW  │         │  BLOCK  │
              │   ↓     │         │   ↓     │
              │  LLM    │         │ Safe    │
              │  API    │         │ Response│
              └─────────┘         └─────────┘
```

---

## Installation

```bash
pip install pygenguard
```

**With Redis support:**
```bash
pip install pygenguard[redis]
```

**Requirements**: Python 3.9+  
**Core Dependencies**: None (pure Python stdlib)

---

## Quickstart (5 minutes)

### Basic Usage (Sync)

```python
from pygenguard import Guard, Session

# 1. Create a guard with your preferred mode
guard = Guard(mode="balanced")  # Options: strict, balanced, permissive

# 2. Create a session from your request context
session = Session.create(
    user_id="user_123",
    ip_address="192.168.1.1",
    user_agent="Mozilla/5.0..."
)

# 3. Inspect every prompt before sending to LLM
decision = guard.inspect(
    prompt=user_input,
    session=session
)

# 4. Act on the decision
if decision.allowed:
    response = call_llm(user_input)
else:
    response = decision.safe_response
    # decision.rationale contains the reason
```

### Async Usage (v0.2.0+) ⚡

```python
from pygenguard import AsyncGuard, Session

# Create async guard
guard = AsyncGuard(mode="balanced")

async def process_chat(user_input: str, user_id: str):
    session = Session.create(user_id=user_id)
    
    # Non-blocking inspection
    decision = await guard.inspect(user_input, session)
    
    if decision.allowed:
        return await call_llm_async(user_input)
    return decision.safe_response
```

### With FastAPI

```python
from fastapi import FastAPI, Request
from pygenguard import AsyncGuard, Session

app = FastAPI()
guard = AsyncGuard(mode="strict")

@app.post("/chat")
async def chat(request: Request, body: ChatRequest):
    session = Session.from_request(request, user_id=body.user_id)
    
    decision = await guard.inspect(body.prompt, session)
    
    if not decision.allowed:
        return {"response": decision.safe_response, "blocked": True}
    
    # Safe to call LLM
    return {"response": await call_llm(body.prompt)}
```

---

## Security Planes

PyGenGuard evaluates every request through 5 security planes (in order):

| Plane | Purpose | Blocks On |
|-------|---------|-----------| 
| **Identity** | Session fingerprint + trust scoring | Fingerprint drift, low trust score |
| **Intent** | Cognitive threat detection | Privilege escalation, coercion, authority spoofing |
| **Context** | Multi-turn attack detection | Split payloads, instruction poisoning |
| **Economics** | Token burn-rate limiting | Denial-of-wallet patterns |
| **Compliance** | PII detection + audit logging | Never blocks, only annotates |

### How IP Address Fingerprinting Works

The **Identity Plane** creates a cryptographic fingerprint from:
- **IP Address** + **User-Agent** + **TLS Fingerprint**

If this fingerprint changes between requests (e.g., user switches networks or VPN), the trust score drops by 50 points. This detects:
- Session hijacking attempts
- Credential theft
- Man-in-the-middle attacks

---

## Plugin System (v0.2.0+) 🔌

Create custom security planes that integrate with the pipeline:

```python
from pygenguard.plugins import BasePlane, PlaneConfig, PlanePhase
from pygenguard.decision import PlaneResult

class ProfanityFilterPlane(BasePlane):
    """Custom plane that blocks profanity."""
    
    BLOCKED_WORDS = {"badword1", "badword2"}
    
    @classmethod
    def get_config(cls) -> PlaneConfig:
        return PlaneConfig(
            name="profanity_filter",
            phase=PlanePhase.POST_INTENT,  # Runs after intent analysis
            priority=10
        )
    
    def evaluate(self, prompt, session, context=None) -> PlaneResult:
        words = set(prompt.lower().split())
        found = words & self.BLOCKED_WORDS
        
        if found:
            return PlaneResult(
                plane_name="profanity_filter",
                passed=False,
                risk_score=0.8,
                details=f"Blocked words: {found}",
                latency_ms=0.1
            )
        
        return PlaneResult(
            plane_name="profanity_filter",
            passed=True,
            risk_score=0.0,
            details="Clean",
            latency_ms=0.1
        )

# Register with AsyncGuard
guard = AsyncGuard(mode="balanced")
guard.register_plugin(ProfanityFilterPlane)
```

### Plugin Execution Phases

| Phase | When it runs |
|-------|-------------|
| `PRE_IDENTITY` | Before any built-in planes |
| `POST_IDENTITY` | After identity, before intent |
| `POST_INTENT` | After intent, before context |
| `POST_CONTEXT` | After context, before economics |
| `POST_ECONOMICS` | After economics, before compliance |
| `POST_COMPLIANCE` | After all built-in planes |

---

## Redis Session Store (v0.2.0+) 🗄️

For distributed deployments, use Redis to share session state:

```python
from pygenguard.adapters import RedisSessionStore

# Connect to Redis
store = RedisSessionStore(
    redis_url="redis://localhost:6379/0",
    key_prefix="myapp:sessions:",
    default_ttl=86400  # 24 hours
)

# Session data is now shared across all instances
```

### Async Redis Store

```python
from pygenguard.adapters import AsyncRedisSessionStore

store = AsyncRedisSessionStore("redis://localhost:6379/0")

# Use with AsyncGuard
session_data = await store.get("user_123")
```

---

## Configuration

All configuration is code-based (no YAML files):

```python
guard = Guard(
    mode="strict",                              # Preset mode
    trust_thresholds={"full": 80, "degraded": 50},  # Custom identity thresholds
    intent_sensitivity=0.3,                     # Lower = stricter
    max_burn_rate=500.0,                        # Tokens/sec limit
    audit_enabled=True                          # JSON audit logging
)
```

### Mode Presets

| Mode | Trust Thresholds | Intent Sensitivity | Burn Rate |
|------|-----------------|-------------------|-----------|
| `strict` | full: 80, degraded: 50 | 0.3 | 500 |
| `balanced` | full: 70, degraded: 40 | 0.5 | 1000 |
| `permissive` | full: 50, degraded: 20 | 0.7 | 2000 |

---

## The Decision Object

Every `inspect()` call returns an immutable `Decision`:

```python
decision = guard.inspect(prompt, session)

decision.allowed          # bool: Can we proceed?
decision.action           # "ALLOW" | "BLOCK" | "DEGRADE" | "CHALLENGE"
decision.rationale        # Human-readable reason
decision.safe_response    # Pre-built response for blocked requests
decision.trace_id         # UUID for audit trail
decision.plane_results    # Per-plane breakdown
decision.to_dict()        # JSON-serializable for logging
```

---

## Audit Logging

Every decision is logged as structured JSON:

```json
{
  "event": "security_decision",
  "trace_id": "abc-123",
  "timestamp": "2026-01-06T09:30:00Z",
  "allowed": false,
  "action": "BLOCK",
  "rationale": "Intent analysis failed: Privilege escalation detected",
  "plane_results": {
    "identity": {"passed": true, "risk_score": 0.0},
    "intent": {"passed": false, "risk_score": 0.75}
  },
  "regulatory": {
    "eu_ai_act": "Article 13 compliant",
    "nist_ai_rmf": "GV-3 logged"
  }
}
```

---

## What PyGenGuard Does NOT Do

- ❌ **No ML model inference** — All checks are rule-based and deterministic
- ❌ **No network calls** — Works fully offline
- ❌ **No content generation** — Only inspection and blocking
- ❌ **No output filtering** — v0.2 is input-only (output guards in v0.3)

---

## License

Apache 2.0 — Enterprise-safe, permissive, no patent traps.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Roadmap

- **v0.1.0**: Core security planes, text-only
- **v0.2.0** (Current): Plugin system, async support, Redis adapters
- **v0.3.0**: Multimodal guards (image, audio), output filtering
- **v0.4.0**: OpenTelemetry tracing, Prometheus metrics
