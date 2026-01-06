# PyGenGuard

**Runtime security and governance framework for GenAI systems.**

PyGenGuard enforces trust, intent, cost, and compliance policies **before and after** model execution. It sits between your application and the LLM, acting as a deterministic security layer.

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

**Requirements**: Python 3.9+  
**Dependencies**: None (pure Python stdlib)

---

## Quickstart (5 minutes)

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

### With FastAPI

```python
from fastapi import FastAPI, Request
from pygenguard import Guard, Session

app = FastAPI()
guard = Guard(mode="strict")

@app.post("/chat")
async def chat(request: Request, body: ChatRequest):
    session = Session.from_request(request, user_id=body.user_id)
    
    decision = guard.inspect(body.prompt, session)
    
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

## What PyGenGuard Does NOT Do

- ❌ **No ML model inference** — All checks are rule-based and deterministic
- ❌ **No network calls** — Works fully offline
- ❌ **No content generation** — Only inspection and blocking
- ❌ **No output filtering** — v0.1 is input-only (output guards in v0.3)
- ❌ **No multimodal** — Text-only in v0.1 (image/audio in v0.3)

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

## License

Apache 2.0 — Enterprise-safe, permissive, no patent traps.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Roadmap

- **v0.1.0** (Current): Core security planes, text-only
- **v0.2.0**: Plugin system, async support, Redis adapters
- **v0.3.0**: Multimodal guards (image, audio)
