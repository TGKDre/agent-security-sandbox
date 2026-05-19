"""
ToolOutputSanitizer
-------------------
Scans every tool return value before it enters the model context window.
Detects and neutralizes two attack classes:
  1. Prompt injection signals — direct override instructions embedded in tool output
  2. Sensitive data patterns — credentials, tokens, and secrets in structured data

Design intent: tool return values are environmental data, not trusted instructions.
This sanitizer enforces that boundary at the data layer before the model sees the content.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Injection signal patterns — phrases that attempt to override agent behavior
# ---------------------------------------------------------------------------
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"disregard\s+(all\s+)?previous\s+instructions?",
    r"forget\s+(all\s+)?previous\s+instructions?",
    r"new\s+instructions?\s*:",
    r"system\s*:\s*you\s+are\s+now",
    r"your\s+new\s+(role|instructions?|directives?)\s+(is|are)\s*:",
    r"override\s+(previous\s+)?(instructions?|prompt|system)",
    r"\[\[\s*injection",
    r"act\s+as\s+(a\s+)?(?:different|new|unrestricted)\s+(ai|assistant|model)",
    r"you\s+are\s+no\s+longer",
    r"from\s+now\s+on\s+(you\s+)?(must|will|should|shall)",
]

# ---------------------------------------------------------------------------
# Sensitive data patterns — credentials and tokens that should never be echoed
# ---------------------------------------------------------------------------
SECRET_PATTERNS = [
    (r"AKIA[A-Z0-9]{16}", "AWS_ACCESS_KEY"),
    (r"(?i)aws.{0,20}secret.{0,20}[=:\s][A-Za-z0-9/+]{40}", "AWS_SECRET_KEY"),
    (r"(?i)tok_[a-zA-Z0-9_\-]{8,}", "SESSION_TOKEN"),
    (r"(?i)sk-[a-zA-Z0-9]{32,}", "API_KEY"),
    (r"(?i)bearer\s+[a-zA-Z0-9\-._~+/]{20,}", "BEARER_TOKEN"),
    (r"(?i)password[\s=:]+[^\s,;\n]{8,}", "PASSWORD"),
    (r"(?i)api[_-]?key[\s=:]+[^\s,;\n]{16,}", "API_KEY"),
    (r"(?i)private[_-]?key[\s=:]+[^\s,;\n]{16,}", "PRIVATE_KEY"),
    (r"(?i)secret[_-]?key[\s=:]+[^\s,;\n]{16,}", "SECRET_KEY"),
    (r"(?i)access[_-]?token[\s=:]+[^\s,;\n]{16,}", "ACCESS_TOKEN"),
    (r"ghp_[a-zA-Z0-9]{36}", "GITHUB_TOKEN"),
    (r"ghs_[a-zA-Z0-9]{36}", "GITHUB_TOKEN"),
]


@dataclass
class SanitizationResult:
    original: str
    sanitized: str
    was_modified: bool
    injection_signals_found: list[str] = field(default_factory=list)
    secrets_found: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.was_modified


class ToolOutputSanitizer:
    """
    Intercepts tool return values and strips/redacts adversarial content
    before it is passed back to the model context.
    """

    def __init__(self, redact_secrets: bool = True, block_injections: bool = True):
        self.redact_secrets = redact_secrets
        self.block_injections = block_injections
        self._injection_re = [
            re.compile(p, re.IGNORECASE | re.MULTILINE)
            for p in INJECTION_PATTERNS
        ]
        self._secret_re = [
            (re.compile(p, re.MULTILINE), label)
            for p, label in SECRET_PATTERNS
        ]

    def sanitize(self, tool_name: str, output: str) -> SanitizationResult:
        """
        Sanitize a single tool output string.
        Returns a SanitizationResult with the cleaned content and metadata.
        """
        result = output
        injection_hits = []
        secret_hits = []

        # --- Injection detection and neutralization ---
        if self.block_injections:
            for pattern in self._injection_re:
                matches = pattern.findall(result)
                if matches:
                    injection_hits.extend(matches)
                    result = pattern.sub(
                        "[INJECTION SIGNAL REMOVED]", result
                    )
                    logger.warning(
                        f"[Sanitizer] Injection signal detected in '{tool_name}' output: {matches}"
                    )

        # --- Secret detection and redaction ---
        if self.redact_secrets:
            for pattern, label in self._secret_re:
                matches = pattern.findall(result)
                if matches:
                    secret_hits.append(label)
                    result = pattern.sub(f"[REDACTED:{label}]", result)
                    logger.warning(
                        f"[Sanitizer] Secret pattern '{label}' detected in '{tool_name}' output — redacted."
                    )

        was_modified = result != output
        return SanitizationResult(
            original=output,
            sanitized=result,
            was_modified=was_modified,
            injection_signals_found=injection_hits,
            secrets_found=secret_hits,
        )

    def sanitize_all(self, tool_results: dict[str, str]) -> dict[str, SanitizationResult]:
        """Sanitize a batch of tool results keyed by tool name."""
        return {
            name: self.sanitize(name, output)
            for name, output in tool_results.items()
        }
