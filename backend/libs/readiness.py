from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReadinessStatus = Literal["ready", "degraded", "not_configured", "unavailable"]


@dataclass(frozen=True)
class ReadinessProbe:
    status: ReadinessStatus
    detail: str | None = None

    @property
    def ready(self) -> bool:
        return self.status == "ready"
