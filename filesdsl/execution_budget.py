from __future__ import annotations

import time

from .errors import DSLTimeoutError


class ExecutionBudget:
    def __init__(self, timeout_s: float | None) -> None:
        if timeout_s is None:
            normalized_timeout: float | None = None
        else:
            if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)):
                raise TypeError("timeout_s must be a number or None")
            normalized_timeout = float(timeout_s)
            if normalized_timeout < 0:
                raise ValueError("timeout_s must be greater than or equal to 0")

        self.start_monotonic = time.monotonic()
        self.deadline_monotonic = (
            None if normalized_timeout is None else self.start_monotonic + normalized_timeout
        )

    def check(self, phase: str) -> None:
        deadline = self.deadline_monotonic
        if deadline is None:
            return

        now = time.monotonic()
        if now <= deadline:
            return

        elapsed = now - self.start_monotonic
        raise DSLTimeoutError(
            f"Timed out after {elapsed:.3f}s in {phase}",
            elapsed_s=elapsed,
            phase=phase,
        )
