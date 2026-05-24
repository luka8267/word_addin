import os

from .bunken_models import PaperSummary

try:
    from citeproc import Citation, CitationItem, CitationStylesBibliography, CitationStylesStyle
    from citeproc.formatter import plain
    from citeproc.source.json import CiteProcJSON
    import citeproc_styles
except ImportError:
    Citation = None
    CitationItem = None
    CitationStylesBibliography = None
    CitationStylesStyle = None
    CiteProcJSON = None
    citeproc_styles = None
    plain = None


CSL_STYLE_ALIASES = {
    "apa": "apa",
    "vancouver": "vancouver",
    "nature": "nature",
    "acs": "american-chemical-society",
    "ieee": "ieee",
    "american-chemical-society": "american-chemical-society",
}


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
    csl_entry = build_csl_bibliography_entry(paper, normalized_style)
    if csl_entry:
        return csl_entry
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
    if normalized.endswith(".csl"):
        normalized = normalized[:-4]
    if normalized in CSL_STYLE_ALIASES:
        return normalized
    if get_csl_style_path(normalized):
        return normalized
    return "vancouver"


def get_csl_style_path(style: str) -> str | None:
    if citeproc_styles is None:
        return None
    style_id = CSL_STYLE_ALIASES.get(style, style)
    style_id = (style_id or "").strip().lower()
    if not style_id:
        return None
    path = os.path.join(os.path.dirname(citeproc_styles.__file__), "styles", f"{style_id}.csl")
    return path if os.path.exists(path) else None


def paper_to_csl_json(paper: PaperSummary) -> dict:
    year = None
    try:
        year = int(paper.year) if paper.year else None
    except (TypeError, ValueError):
        year = None
    csl_type = {
        "journalArticle": "article-journal",
        "book": "book",
        "bookSection": "chapter",
        "webpage": "webpage",
        "thesis": "thesis",
        "report": "report",
    }.get(paper.item_type or "journalArticle", "article-journal")
    item = {
        "id": str(paper.id),
        "type": csl_type,
        "title": paper.title or "",
        "container-title": paper.journal or "",
        "volume": paper.volume or "",
        "issue": paper.issue or "",
        "page": paper.pages or "",
        "publisher": paper.publisher or "",
        "DOI": normalize_doi_value(paper.doi),
        "author": parse_csl_authors(paper.authors),
    }
    if year:
        item["issued"] = {"date-parts": [[year]]}
    return {key: value for key, value in item.items() if value not in ("", [], None)}


def parse_csl_authors(authors: str) -> list[dict]:
    csl_authors = []
    for name in [part.strip() for part in (authors or "").replace(";", ",").split(",") if part.strip()]:
        parts = name.split()
        if len(parts) >= 2:
            csl_authors.append({"family": parts[-1], "given": " ".join(parts[:-1])})
        else:
            csl_authors.append({"family": name})
    return csl_authors


def build_csl_bibliography_entry(paper: PaperSummary, style: str) -> str | None:
    if not all([Citation, CitationItem, CitationStylesBibliography, CitationStylesStyle, CiteProcJSON, plain]):
        return None
    style_path = get_csl_style_path(style)
    if not style_path:
        return None
    try:
        item = paper_to_csl_json(paper)
        source = CiteProcJSON([item])
        csl_style = CitationStylesStyle(style_path, validate=False)
        bibliography = CitationStylesBibliography(csl_style, source, plain)
        citation = Citation([CitationItem(item["id"])])
        bibliography.register(citation)
        entries = bibliography.bibliography()
    except Exception:
        return None
    if not entries:
        return None
    return append_missing_csl_doi(str(entries[0]).strip(), paper, style)


def append_missing_csl_doi(text: str, paper: PaperSummary, style: str) -> str:
    doi = normalize_doi_value(paper.doi)
    if not doi or doi.lower() in text.lower():
        return text
    if style in {"apa", "elsevier-harvard", "chicago-author-date"}:
        return f"{text} https://doi.org/{doi}"
    return f"{text} doi: {doi}"


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
    normalized = normalize_doi_value(doi)
    if not normalized:
        return ""
    doi_url = f"https://doi.org/{normalized}"
    if style == "apa":
        return f" {doi_url}"
    return f" doi: {normalized}"


def normalize_doi_value(doi: str | None) -> str:
    normalized = (doi or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.lower().startswith(prefix):
            normalized = normalized[len(prefix):].strip()
    return normalized
