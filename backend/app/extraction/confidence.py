"""Conservative signal score, not a calibrated probability or a model-provided number."""


def score(*, table_match: bool, label_match: bool, quality: float, visual: bool, normalized: bool, repetitions: int = 1) -> float:
    base = 0.96 if table_match else 0.94 if label_match else 0.80
    base = min(base, 0.86) if visual else base * quality
    if normalized:
        base -= 0.04
    return round(min(0.99, base + min(0.03, max(0, repetitions - 1) * 0.01)), 3)
