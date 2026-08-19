"""Iris-owned dispatch for narrow read-only conversational capabilities.

The language model may ask Iris to answer a question, but it never receives a
provider handle. This module owns the allowlist and refuses every capability
that is not explicitly classed as read-only.
"""
from __future__ import annotations

import dataclasses
import enum
from collections.abc import Callable


class CapabilityMode(enum.StrEnum):
    READ_ONLY = "read_only"
    PROPOSAL_ONLY = "proposal_only"
    CONSEQUENTIAL = "consequential"


class CapabilityError(RuntimeError):
    """A safe user-facing capability failure."""


@dataclasses.dataclass(frozen=True)
class CapabilityRequest:
    name: str
    arguments: dict[str, str]


@dataclasses.dataclass(frozen=True)
class CapabilityResult:
    text: str
    source: str
    observed_at: str


@dataclasses.dataclass(frozen=True)
class RegisteredCapability:
    mode: CapabilityMode
    handler: Callable[[CapabilityRequest], CapabilityResult]


class CapabilityBroker:
    """Dispatch registered read-only capabilities and fail closed otherwise."""

    def __init__(self, capabilities: dict[str, RegisteredCapability] | None = None):
        self._capabilities = dict(capabilities or {})

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        capability = self._capabilities.get(request.name)
        if capability is None:
            raise CapabilityError("That capability is not available.")
        if capability.mode is not CapabilityMode.READ_ONLY:
            raise CapabilityError("That request needs an explicit Iris command and approval.")
        try:
            result = capability.handler(request)
        except CapabilityError:
            raise
        except Exception:
            raise CapabilityError("That capability is unavailable right now.") from None
        if not isinstance(result, CapabilityResult):
            raise CapabilityError("That capability returned an invalid response.")
        if not result.text or not result.source or not result.observed_at:
            raise CapabilityError("That capability returned an incomplete response.")
        return result
