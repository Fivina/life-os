from __future__ import annotations

from statistics import mean


def brier_score(predictions: list[float], labels: list[bool]) -> float | None:
    if not predictions or len(predictions) != len(labels):
        return None
    return round(mean((max(0.0, min(1.0, prediction)) - (1.0 if label else 0.0)) ** 2 for prediction, label in zip(predictions, labels)), 5)


def mean_absolute_error(predictions: list[float], labels: list[float]) -> float | None:
    if not predictions or len(predictions) != len(labels):
        return None
    return round(mean(abs(prediction - label) for prediction, label in zip(predictions, labels)), 5)


def baseline_completion_rate(labels: list[bool]) -> float:
    if not labels:
        return 0.5
    return sum(1 for label in labels if label) / len(labels)


def baseline_capacity_ratio(labels: list[float]) -> float:
    if not labels:
        return 1.0
    return sum(labels) / len(labels)
