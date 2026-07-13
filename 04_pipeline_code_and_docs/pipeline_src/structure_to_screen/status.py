"""
Structured status contract for the structure-to-screen pipeline.

Every module returns a ModuleResult. The `status` field is the machine-readable
signal an orchestrating agent reasons over — it is NEVER free prose.

    ok            -> module produced a trustworthy result; continue.
    low_confidence -> module produced a result, but a quantified check fell
                     below threshold; downstream may proceed WITH the caveat
                     attached, or an agent may choose to escalate.
    unscreenable  -> module cannot produce a usable result for this target
                     (e.g. no liganded homolog found, no structure available).
                     The pipeline short-circuits; the agent is told why.

This is the contract that makes the tool "agent-callable": an agent can branch
on status.value, read `confidence` for a number, and read `reason` for a
human-facing explanation, without parsing logs.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any
import json
import time


class Status(str, Enum):
    OK = "ok"
    LOW_CONFIDENCE = "low_confidence"
    UNSCREENABLE = "unscreenable"

    def __str__(self) -> str:  # so json/format shows the bare value
        return self.value


# Statuses that permit the pipeline to continue to the next module.
CONTINUABLE = {Status.OK, Status.LOW_CONFIDENCE}


@dataclass
class ModuleResult:
    """The single return type of every pipeline module."""
    module: str                       # module id, e.g. "M4_site"
    status: Status                    # ok | low_confidence | unscreenable
    reason: str = ""                  # one-line human-facing explanation
    confidence: float | None = None   # module-specific numeric score in [0,1] when meaningful
    data: dict[str, Any] = field(default_factory=dict)      # structured payload for downstream
    artifacts: list[str] = field(default_factory=list)      # file paths this module wrote
    metrics: dict[str, Any] = field(default_factory=dict)   # quantitative diagnostics
    elapsed_s: float | None = None

    def __post_init__(self):
        # Allow callers to pass a bare string; coerce to the enum.
        if not isinstance(self.status, Status):
            self.status = Status(str(self.status))

    @property
    def can_continue(self) -> bool:
        return self.status in CONTINUABLE

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def __str__(self) -> str:
        c = f" conf={self.confidence:.2f}" if self.confidence is not None else ""
        return f"[{self.module}] {self.status.value}{c} :: {self.reason}"


def ok(module, reason="", confidence=None, **kw) -> ModuleResult:
    return ModuleResult(module, Status.OK, reason, confidence, **kw)


def low_confidence(module, reason="", confidence=None, **kw) -> ModuleResult:
    return ModuleResult(module, Status.LOW_CONFIDENCE, reason, confidence, **kw)


def unscreenable(module, reason="", **kw) -> ModuleResult:
    return ModuleResult(module, Status.UNSCREENABLE, reason, **kw)


@dataclass
class RunManifest:
    """Top-level record of a full pipeline run — the object an agent inspects."""
    target: str
    modulator: str
    started_at: float = field(default_factory=time.time)
    results: list[ModuleResult] = field(default_factory=list)

    def add(self, r: ModuleResult) -> ModuleResult:
        self.results.append(r)
        return r

    @property
    def overall_status(self) -> Status:
        if any(r.status is Status.UNSCREENABLE for r in self.results):
            return Status.UNSCREENABLE
        if any(r.status is Status.LOW_CONFIDENCE for r in self.results):
            return Status.LOW_CONFIDENCE
        return Status.OK

    @property
    def last(self) -> ModuleResult | None:
        return self.results[-1] if self.results else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "modulator": self.modulator,
            "started_at": self.started_at,
            "overall_status": self.overall_status.value,
            "n_modules_run": len(self.results),
            "reached_module": self.last.module if self.last else None,
            "results": [r.to_dict() for r in self.results],
        }

    def save(self, path: str) -> str:
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        return path
