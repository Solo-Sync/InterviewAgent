from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
_logging_configured = False
_record_factory_configured = False
_base_record_factory = logging.getLogRecordFactory()


def new_trace_id() -> str:
    return f"trc_{uuid4().hex}"


def set_trace_id(trace_id: str) -> Token[str | None]:
    return _trace_id_var.set(trace_id)


def reset_trace_id(token: Token[str | None]) -> None:
    _trace_id_var.reset(token)


def get_trace_id() -> str | None:
    return _trace_id_var.get()


class JsonFormatter(logging.Formatter):
    _reserved = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in (
            "event_type",
            "trace_id",
            "session_id",
            "turn_id",
            "candidate_id",
            "method",
            "path",
            "status_code",
            "latency_ms",
            "stage",
            "state_before",
            "state_after",
            "next_action",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        for key, value in record.__dict__.items():
            if key in self._reserved or key in payload or key.startswith("_"):
                continue
            if callable(value):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    global _logging_configured, _record_factory_configured
    if not _record_factory_configured:
        def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = _base_record_factory(*args, **kwargs)
            if not hasattr(record, "trace_id") or record.trace_id is None:
                record.trace_id = get_trace_id()
            return record

        logging.setLogRecordFactory(record_factory)
        _record_factory_configured = True

    if _logging_configured:
        return

    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._observability_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    if root.level > logging.INFO:
        root.setLevel(logging.INFO)
    _logging_configured = True


def log_event(logger: logging.Logger, level: int, event_type: str, **fields: Any) -> None:
    logger.log(level, event_type, extra={"event_type": event_type, **fields})


def _escape_label_value(value: Any) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _label_text(label_names: tuple[str, ...], label_values: tuple[str, ...]) -> str:
    if not label_names:
        return ""
    parts = [f'{name}="{_escape_label_value(value)}"' for name, value in zip(label_names, label_values, strict=True)]
    return "{" + ",".join(parts) + "}"


class CounterMetric:
    def __init__(self, name: str, description: str, label_names: tuple[str, ...] = ()) -> None:
        self.name = name
        self.description = description
        self.label_names = label_names
        self._values: dict[tuple[str, ...], float] = {}
        self._lock = Lock()

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        label_values = tuple(labels[name] for name in self.label_names)
        with self._lock:
            self._values[label_values] = self._values.get(label_values, 0.0) + amount

    def render(self) -> str:
        lines = [f"# HELP {self.name} {self.description}", f"# TYPE {self.name} counter"]
        with self._lock:
            items = sorted(self._values.items())
        for label_values, value in items:
            lines.append(f"{self.name}{_label_text(self.label_names, label_values)} {value}")
        return "\n".join(lines)


class HistogramMetric:
    def __init__(
        self,
        name: str,
        description: str,
        label_names: tuple[str, ...] = (),
        buckets: tuple[float, ...] = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    ) -> None:
        self.name = name
        self.description = description
        self.label_names = label_names
        self.buckets = buckets
        self._counts: dict[tuple[str, ...], list[int]] = {}
        self._sums: dict[tuple[str, ...], float] = {}
        self._totals: dict[tuple[str, ...], int] = {}
        self._lock = Lock()

    def observe(self, value: float, **labels: str) -> None:
        label_values = tuple(labels[name] for name in self.label_names)
        with self._lock:
            bucket_counts = self._counts.setdefault(label_values, [0] * len(self.buckets))
            for index, upper_bound in enumerate(self.buckets):
                if value <= upper_bound:
                    bucket_counts[index] += 1
            self._sums[label_values] = self._sums.get(label_values, 0.0) + value
            self._totals[label_values] = self._totals.get(label_values, 0) + 1

    def render(self) -> str:
        lines = [f"# HELP {self.name} {self.description}", f"# TYPE {self.name} histogram"]
        with self._lock:
            keys = sorted(self._totals)
            counts = {key: list(self._counts.get(key, [0] * len(self.buckets))) for key in keys}
            sums = {key: self._sums.get(key, 0.0) for key in keys}
            totals = {key: self._totals.get(key, 0) for key in keys}
        for label_values in keys:
            bucket_counts = counts[label_values]
            for index, upper_bound in enumerate(self.buckets):
                labels = {
                    **dict(zip(self.label_names, label_values, strict=True)),
                    "le": f"{upper_bound:g}",
                }
                metric_labels = tuple(labels[name] for name in (*self.label_names, "le"))
                lines.append(
                    f"{self.name}_bucket{_label_text((*self.label_names, 'le'), metric_labels)} {bucket_counts[index]}"
                )
            plus_inf_labels = {
                **dict(zip(self.label_names, label_values, strict=True)),
                "le": "+Inf",
            }
            plus_inf_metric_labels = tuple(plus_inf_labels[name] for name in (*self.label_names, "le"))
            lines.append(
                f"{self.name}_bucket{_label_text((*self.label_names, 'le'), plus_inf_metric_labels)} {totals[label_values]}"
            )
            lines.append(f"{self.name}_sum{_label_text(self.label_names, label_values)} {sums[label_values]}")
            lines.append(f"{self.name}_count{_label_text(self.label_names, label_values)} {totals[label_values]}")
        return "\n".join(lines)


http_requests_total = CounterMetric(
    "http_requests_total",
    "Total number of HTTP requests handled by the API.",
    ("method", "path", "status_code"),
)
http_request_duration_seconds = HistogramMetric(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ("method", "path", "status_code"),
)
turn_stage_latency_seconds = HistogramMetric(
    "turn_stage_latency_seconds",
    "Latency for each interview turn stage in seconds.",
    ("stage",),
)
turn_total_latency_seconds = HistogramMetric(
    "turn_total_latency_seconds",
    "Total latency for a single interview turn in seconds.",
)


def observe_http_request(*, method: str, path: str, status_code: int, duration_seconds: float) -> None:
    labels = {
        "method": method,
        "path": path,
        "status_code": str(status_code),
    }
    http_requests_total.inc(**labels)
    http_request_duration_seconds.observe(duration_seconds, **labels)


def observe_turn_stage(stage: str, duration_seconds: float) -> None:
    turn_stage_latency_seconds.observe(duration_seconds, stage=stage)


def observe_turn_total(duration_seconds: float) -> None:
    turn_total_latency_seconds.observe(duration_seconds)


def render_metrics() -> str:
    return "\n".join(
        [
            http_requests_total.render(),
            http_request_duration_seconds.render(),
            turn_stage_latency_seconds.render(),
            turn_total_latency_seconds.render(),
            "",
        ]
    )
