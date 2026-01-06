# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-01-06

### Added
- **Plugin System**
  - `BasePlane` abstract class for creating custom security planes
  - `PlaneRegistry` for managing plane registration
  - `PlaneConfig` with phase-based execution (PRE_IDENTITY → POST_COMPLIANCE)
  - `PluginLoader` for dynamic loading from modules, files, and entry points
  - `@plane_plugin` decorator for global registration

- **Async Support**
  - `AsyncGuard` class with full async/await support
  - `inspect()` coroutine for non-blocking evaluation
  - `inspect_batch()` for concurrent processing of multiple requests
  - `inspect_sync()` wrapper for calling from synchronous code
  - Thread pool executor for CPU-bound plane operations
  - `AsyncBatcher` utility for efficient batch processing

- **Session Store Adapters**
  - `BaseSessionStore` abstract interface
  - `InMemorySessionStore` with TTL and thread-safety
  - `RedisSessionStore` for distributed deployments
  - `AsyncRedisSessionStore` for high-concurrency async apps
  - `SessionData` serializable dataclass
  - Atomic Lua scripts for Redis trust score updates

- **Utilities**
  - `run_sync()` - run coroutines from sync code
  - `maybe_await()` - handle both sync and async values
  - `@async_to_sync` and `@sync_to_async` decorators

### Changed
- Core `Guard` remains fully synchronous and zero-dependency
- Optional `redis>=4.2.0` dependency for Redis adapter

### Security
- IP address + User-Agent + TLS fingerprint for identity tracking
- Fingerprint drift detection prevents session hijacking

---

## [0.1.0] - 2026-01-06

### Added
- **Core Framework**
  - `Guard` class with single `inspect()` entry point
  - `Session` for request context encapsulation
  - `Decision` immutable result object with full audit trail

- **Security Planes**
  - Identity Plane: Continuous Trust Scoring (CTS) with fingerprint drift detection
  - Intent Plane: Cognitive threat detection (authority spoofing, coercion, emotional manipulation, privilege escalation)
  - Context Plane: Multi-turn attack detection (split payloads, instruction poisoning)
  - Economics Plane: Token burn-rate throttling for denial-of-wallet protection
  - Compliance Plane: PII detection with regulatory tagging (EU AI Act, NIST AI RMF)

- **Audit System**
  - JSON structured logging for forensics and compliance
  - Regulatory audit trail (EU AI Act Article 13, NIST AI RMF GV-3)

- **Configuration**
  - Mode presets: `strict`, `balanced`, `permissive`
  - Code-configurable thresholds (no YAML files)

### Security
- Deterministic behavior (no network calls, no async complexity)
- Works fully offline
- Zero heavy dependencies (pure Python stdlib)

---

## Roadmap

### [0.3.0] - Planned
- Multimodal guards (image, audio)
- CLIP-based visual safety (optional dependency)
- Whisper-based audio analysis (optional dependency)

### [0.4.0] - Planned
- OpenTelemetry tracing integration
- Prometheus metrics export
- Dashboard UI template

