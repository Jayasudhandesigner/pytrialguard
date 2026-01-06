# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### [0.2.0] - Planned
- Plugin system for custom planes
- Async support (optional)
- Redis session store adapter

### [0.3.0] - Planned
- Multimodal guards (image, audio)
- CLIP-based visual safety (optional dependency)
- Whisper-based audio analysis (optional dependency)
