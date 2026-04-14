import json
import os
import sqlite3
from pathlib import Path

from .bunken_models import PaperSummary


DB_PATH = Path(os.getenv("BUNKEN_DB_PATH", str(Path(__file__).resolve().parents[3] / "papers.db")))
DEFAULT_USER_ID = int(os.getenv("BUNKEN_DEFAULT_USER_ID", "1"))
SAMPLE_DATA_PATH = Path(__file__).resolve().with_name("sample_papers.json")


def resolve_user_id() -> int:
    return DEFAULT_USER_ID


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def load_sample_papers() -> list[PaperSummary]:
    if not SAMPLE_DATA_PATH.exists():
        return []
    items = json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))
    return [
        PaperSummary(
            id=str(item["id"]),
            title=item.get("title", ""),
            authors=item.get("authors", ""),
            journal=item.get("journal", ""),
            year=int(item.get("year", 0) or 0),
            doi=item.get("doi"),
        )
        for item in items
    ]


def use_sample_data() -> bool:
    return not DB_PATH.exists()


def search_user_papers(user_id: int, query: str) -> list[PaperSummary]:
    if use_sample_data():
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
    normalized_query = f"%{(query or '').strip()}%"
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, authors, journal, year
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
        )
        for row in rows
    ]


def fetch_papers_by_ids(user_id: int, paper_ids: list[str]) -> list[PaperSummary]:
    if not paper_ids:
        return []
    if use_sample_data():
        by_id = {paper.id: paper for paper in load_sample_papers()}
        return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]
    placeholders = ",".join("?" for _ in paper_ids)
    params = [user_id, *paper_ids]
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT id, title, authors, journal, year
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
        )
        for row in rows
    }
    return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]
