import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .bunken_models import PaperSummary


DB_PATH = Path(os.getenv("BUNKEN_DB_PATH", str(Path(__file__).resolve().parents[3] / "papers.db")))
DEFAULT_USER_ID = os.getenv("BUNKEN_DEFAULT_USER_ID", "1")
DEFAULT_EMAIL = os.getenv("BUNKEN_DEFAULT_EMAIL", "")
DEFAULT_USERNAME = os.getenv("BUNKEN_DEFAULT_USERNAME", "cloud-user")
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""
SAMPLE_DATA_PATH = Path(__file__).resolve().with_name("sample_papers.json")


def resolve_user_id() -> str:
    return DEFAULT_USER_ID


def resolve_user_profile() -> dict[str, str]:
    return {
        "userId": DEFAULT_USER_ID,
        "email": DEFAULT_EMAIL,
        "username": DEFAULT_USERNAME,
    }


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def load_sample_papers() -> list[PaperSummary]:
    if not SAMPLE_DATA_PATH.exists():
        return []
    items = json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))
    return [paper_from_mapping(item) for item in items]


def use_supabase() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def use_sqlite() -> bool:
    return DB_PATH.exists()


def paper_from_mapping(item: dict) -> PaperSummary:
    return PaperSummary(
        id=str(item.get("id", "")),
        title=item.get("title", "") or "",
        authors=item.get("authors", "") or "",
        journal=item.get("journal", "") or "",
        year=int(item.get("year", 0) or 0),
        doi=item.get("doi"),
    )


def request_supabase(path: str, query_params: dict[str, str]) -> list[dict]:
    url = f"{SUPABASE_URL}{path}?{urlencode(query_params, safe='(),.*')}"
    request = Request(
        url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase request failed: {error.code} {error_body}") from error


def search_user_papers(user_id: str, query: str) -> list[PaperSummary]:
    if use_supabase():
        normalized_query = (query or "").strip()
        params = {
            "select": "id,title,authors,journal,year,doi",
            "user_id": f"eq.{user_id}",
            "order": "display_order.asc.nullslast,id.asc",
        }
        if normalized_query:
            escaped_query = normalized_query.replace("%", r"\%").replace(",", r"\,")
            params["or"] = (
                f"(title.ilike.*{escaped_query}*,"
                f"authors.ilike.*{escaped_query}*,"
                f"journal.ilike.*{escaped_query}*)"
            )
        rows = request_supabase("/rest/v1/papers", params)
        return [paper_from_mapping(row) for row in rows]

    if use_sqlite():
        normalized_query = f"%{(query or '').strip()}%"
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, title, authors, journal, year, doi
                FROM papers
                WHERE user_id = ?
                  AND (
                    ? = '%%'
                    OR title LIKE ?
                    OR authors LIKE ?
                    OR journal LIKE ?
                  )
                ORDER BY COALESCE(display_order, id)
                """,
                (user_id, normalized_query, normalized_query, normalized_query, normalized_query),
            ).fetchall()
        return [
            PaperSummary(
                id=str(row["id"]),
                title=row["title"] or "",
                authors=row["authors"] or "",
                journal=row["journal"] or "",
                year=int(row["year"] or 0),
                doi=row["doi"],
            )
            for row in rows
        ]

    normalized_query = (query or "").strip().lower()
    papers = load_sample_papers()
    if not normalized_query:
        return papers
    return [
        paper
        for paper in papers
        if normalized_query in paper.title.lower()
        or normalized_query in paper.authors.lower()
        or normalized_query in paper.journal.lower()
    ]


def fetch_papers_by_ids(user_id: str, paper_ids: list[str]) -> list[PaperSummary]:
    if not paper_ids:
        return []

    if use_supabase():
        csv_ids = ",".join(paper_ids)
        rows = request_supabase(
            "/rest/v1/papers",
            {
                "select": "id,title,authors,journal,year,doi",
                "user_id": f"eq.{user_id}",
                "id": f"in.({csv_ids})",
            },
        )
        by_id = {str(row["id"]): paper_from_mapping(row) for row in rows}
        return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]

    if use_sqlite():
        placeholders = ",".join("?" for _ in paper_ids)
        params = [user_id, *paper_ids]
        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT id, title, authors, journal, year, doi
                FROM papers
                WHERE user_id = ?
                  AND id IN ({placeholders})
                """,
                params,
            ).fetchall()
        by_id = {
            str(row["id"]): PaperSummary(
                id=str(row["id"]),
                title=row["title"] or "",
                authors=row["authors"] or "",
                journal=row["journal"] or "",
                year=int(row["year"] or 0),
                doi=row["doi"],
            )
            for row in rows
        }
        return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]

    by_id = {paper.id: paper for paper in load_sample_papers()}
    return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]
