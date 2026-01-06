"""
Hashing utilities for cryptographic operations.
"""

import hashlib


def compute_fingerprint(data: str) -> str:
    """
    Compute a SHA-256 fingerprint of input data.
    
    Returns first 16 characters for brevity.
    """
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def compute_full_hash(data: bytes) -> str:
    """
    Compute full SHA-256 hash of binary data.
    """
    return hashlib.sha256(data).hexdigest()


def verify_hash(data: bytes, expected_hash: str) -> bool:
    """
    Verify data matches expected hash.
    """
    return compute_full_hash(data) == expected_hash
