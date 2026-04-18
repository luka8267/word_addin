from .bunken_models import PaperSummary


def build_in_text_citation(paper: PaperSummary, style: str, locator: str | None = None) -> str:
    normalized_style = normalize_style(style)
    lead_author = first_author_label(paper.authors)
    if normalized_style in {"vancouver", "acs", "nature", "ieee"}:
        locator_part = f", {locator}" if locator else ""
        return f"[{paper.id}{locator_part}]"
    locator_part = f", {locator}" if locator else ""
    return f"({lead_author}, {paper.year}{locator_part})"


def build_bibliography_entry(paper: PaperSummary, style: str) -> str:
    normalized_style = normalize_style(style)
    if normalized_style == "ieee":
        return f'{paper.authors}, "{paper.title}," {paper.journal}, {paper.year}.'
    if normalized_style == "acs":
        return f"{paper.authors}. {paper.title}. {paper.journal} {paper.year}."
    if normalized_style == "vancouver":
        return f"{paper.authors}. {paper.title}. {paper.journal}. {paper.year}."
    if normalized_style == "nature":
        return f"{paper.authors} {paper.title}. {paper.journal} ({paper.year})."
    return f"{paper.authors} ({paper.year}). {paper.title}. {paper.journal}."


def normalize_style(style: str) -> str:
    normalized = (style or "").strip().lower()
    if normalized in {"vancouver", "apa", "acs", "nature", "ieee"}:
        return normalized
    return "vancouver"


def first_author_label(authors: str) -> str:
    parts = [part.strip() for part in (authors or "").split(",") if part.strip()]
    return parts[0] if parts else "Unknown"
