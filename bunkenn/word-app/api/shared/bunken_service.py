from .bunken_models import PaperSummary


def build_in_text_citation(paper: PaperSummary, style: str, locator: str | None = None) -> str:
    normalized_style = normalize_style(style)
    lead_author = author_year_label(paper.authors)
    year = year_label(paper.year)
    if normalized_style in {"vancouver", "acs", "nature", "ieee"}:
        locator_part = f", {locator}" if locator else ""
        return f"[{paper.id}{locator_part}]"
    locator_part = f", {locator}" if locator else ""
    return f"({lead_author}, {year}{locator_part})"


def build_bibliography_entry(paper: PaperSummary, style: str) -> str:
    normalized_style = normalize_style(style)
    authors = bibliography_authors(paper.authors, normalized_style)
    year = year_label(paper.year)
    doi = doi_suffix(paper.doi, normalized_style)
    publication = publication_label(paper, normalized_style)
    if normalized_style == "ieee":
        return f'{authors}, "{paper.title}," {publication}, {year}.{doi}'
    if normalized_style == "acs":
        return f"{authors}. {paper.title}. {publication} {year}.{doi}"
    if normalized_style == "vancouver":
        return f"{authors}. {paper.title}. {publication}. {year}.{doi}"
    if normalized_style == "nature":
        return f"{authors} {paper.title}. {publication} ({year}).{doi}"
    return f"{authors} ({year}). {paper.title}. {publication}.{doi}"


def normalize_style(style: str) -> str:
    normalized = (style or "").strip().lower()
    if normalized in {"vancouver", "apa", "acs", "nature", "ieee"}:
        return normalized
    return "vancouver"


def first_author_label(authors: str) -> str:
    parts = parse_authors(authors)
    return parts[0] if parts else "Unknown"


def author_year_label(authors: str) -> str:
    parts = parse_authors(authors)
    if not parts:
        return "Unknown"
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} & {parts[1]}"
    return f"{parts[0]} et al."


def bibliography_authors(authors: str, style: str) -> str:
    parts = parse_authors(authors)
    if not parts:
        return "Unknown"
    if style == "apa":
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2:
            return f"{parts[0]} & {parts[1]}"
        return ", ".join(parts[:-1]) + f", & {parts[-1]}"
    return ", ".join(parts)


def parse_authors(authors: str) -> list[str]:
    normalized = (authors or "").replace(";", ",")
    return [part.strip() for part in normalized.split(",") if part.strip()]


def year_label(year: int | str | None) -> str:
    return str(year) if year else "n.d."


def publication_label(paper: PaperSummary, style: str) -> str:
    label = paper.journal or paper.publisher or ""
    volume = (paper.volume or "").strip()
    issue = (paper.issue or "").strip()
    pages = (paper.pages or "").strip()
    if volume:
        volume_part = volume
        if issue:
            volume_part += f"({issue})"
        separator = " " if style in {"apa", "acs"} else ", "
        label = f"{label}{separator}{volume_part}" if label else volume_part
    if pages:
        page_separator = ", " if label else ""
        label = f"{label}{page_separator}{pages}"
    return label or "Unknown"


def doi_suffix(doi: str | None, style: str) -> str:
    normalized = (doi or "").strip()
    if not normalized:
        return ""
    if normalized.lower().startswith("http"):
        doi_url = normalized
    else:
        doi_url = f"https://doi.org/{normalized}"
    if style == "apa":
        return f" {doi_url}"
    return f" doi: {normalized.removeprefix('https://doi.org/').removeprefix('http://doi.org/')}"
