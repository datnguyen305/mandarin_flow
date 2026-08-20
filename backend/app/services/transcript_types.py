from dataclasses import dataclass


@dataclass(frozen=True)
class RawSubtitle:
    start: float
    end: float
    text: str
