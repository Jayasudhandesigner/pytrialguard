"""
Audit Logger - JSON structured logging for compliance.

Produces audit-ready logs for EU AI Act, NIST AI RMF, SOC2.
"""

import json
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path


class AuditLogger:
    """
    Structured JSON logger for security decisions.
    
    Every decision is logged with full context for:
    - Regulatory audits
    - Forensic investigation
    - Analytics
    """
    
    def __init__(
        self, 
        enabled: bool = True,
        log_file: Optional[str] = None,
        log_level: int = logging.INFO
    ):
        """
        Args:
            enabled: Whether logging is active
            log_file: Path to log file (None = stdout only)
            log_level: Python logging level
        """
        self.enabled = enabled
        self._logger = logging.getLogger("pygenguard.audit")
        self._logger.setLevel(log_level)
        
        # Avoid duplicate handlers
        if not self._logger.handlers:
            # Console handler
            console = logging.StreamHandler()
            console.setFormatter(logging.Formatter('%(message)s'))
            self._logger.addHandler(console)
            
            # File handler if specified
            if log_file:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(logging.Formatter('%(message)s'))
                self._logger.addHandler(file_handler)
    
    def log(self, decision) -> None:
        """
        Log a Decision object as structured JSON.
        
        Output format is designed for log aggregators (Datadog, Splunk, etc.)
        """
        if not self.enabled:
            return
        
        log_entry = {
            "event": "security_decision",
            "version": "1.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **decision.to_dict(),
            "regulatory": {
                "eu_ai_act": "Article 13 compliant",
                "nist_ai_rmf": "GV-3 logged"
            }
        }
        
        self._logger.info(json.dumps(log_entry, separators=(',', ':')))
    
    def log_event(self, event_type: str, details: dict) -> None:
        """Log a custom event."""
        if not self.enabled:
            return
        
        log_entry = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **details
        }
        
        self._logger.info(json.dumps(log_entry, separators=(',', ':')))
