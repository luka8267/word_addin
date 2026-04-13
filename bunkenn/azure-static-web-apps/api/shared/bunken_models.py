from dataclasses import asdict, dataclass


@dataclass
class PaperSummary:
    id: str
    title: str
    authors: str
    journal: str
    year: int
    doi: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
