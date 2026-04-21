from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

MetricLabels = tuple[tuple[str, str], ...]
MetricKey = tuple[str, MetricLabels]


@dataclass
class SummaryStats:
    count: int = 0
    total: float = 0.0
    minimum: float | None = None
    maximum: float | None = None

    def add(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    def as_dict(self) -> dict:
        avg = (self.total / self.count) if self.count else 0.0
        return {
            "count": self.count,
            "total": round(self.total, 6),
            "avg": round(avg, 6),
            "min": round(self.minimum, 6) if self.minimum is not None else None,
            "max": round(self.maximum, 6) if self.maximum is not None else None,
        }


class InMemoryMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[MetricKey, int] = {}
        self._summaries: dict[MetricKey, SummaryStats] = {}

    @staticmethod
    def _normalize_labels(labels: dict[str, object]) -> MetricLabels:
        return tuple(sorted((str(k), str(v)) for k, v in labels.items()))

    def inc(self, name: str, amount: int = 1, **labels: object) -> None:
        key: MetricKey = (name, self._normalize_labels(labels))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + amount

    def observe(self, name: str, value: float, **labels: object) -> None:
        key: MetricKey = (name, self._normalize_labels(labels))
        with self._lock:
            summary = self._summaries.get(key)
            if summary is None:
                summary = SummaryStats()
                self._summaries[key] = summary
            summary.add(float(value))

    def snapshot(self) -> dict:
        with self._lock:
            counters = [
                {
                    "name": name,
                    "labels": dict(label_pairs),
                    "value": value,
                }
                for (name, label_pairs), value in sorted(self._counters.items(), key=lambda i: (i[0][0], i[0][1]))
            ]
            summaries = [
                {
                    "name": name,
                    "labels": dict(label_pairs),
                    "stats": stats.as_dict(),
                }
                for (name, label_pairs), stats in sorted(self._summaries.items(), key=lambda i: (i[0][0], i[0][1]))
            ]
        return {"counters": counters, "summaries": summaries}


metrics = InMemoryMetrics()
