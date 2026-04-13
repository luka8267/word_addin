from .bunken_models import PaperSummary


def build_in_text_citation(paper: PaperSummary, style: str, locator: str | None = None) -> str:
    lead_author = first_author_label(paper.authors)
    if style == "vancouver":
        locator_part = f", {locator}" if locator else ""
        return f"[{paper.id}{locator_part}]"
    locator_part = f", {locator}" if locator else ""
    return f"({lead_author}, {paper.year}{locator_part})"


def build_bibliography_entry(paper: PaperSummary, style: str) -> str:
    if style == "vancouver":
        return f"{paper.authors}. {paper.title}. {paper.journal}. {paper.year}."
    if style == "nature":
        return f"{paper.authors} {paper.title}. {paper.journal} ({paper.year})."
    return f"{paper.authors} ({paper.year}). {paper.title}. {paper.journal}."


def first_author_label(authors: str) -> str:
    parts = [part.strip() for part in (authors or "").split(",") if part.strip()]
    return parts[0] if parts else "Unknown"
