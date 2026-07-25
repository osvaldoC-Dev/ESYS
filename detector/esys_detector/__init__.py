"""
ESYS Detector — core inspection engine.

Inspects outbound request payloads for secrets and PII before they leave
the organization through an AI model provider, and returns a policy
decision: allow / redact / block.

V1 scope only. See docs/scope.md for what this intentionally does NOT do.
"""

__version__ = "0.1.0"
