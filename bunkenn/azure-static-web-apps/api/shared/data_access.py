import os
import sqlite3
from pathlib import Path

from .bunken_models import PaperSummary


DB_PATH = Path(os.getenv("BUNKEN_DB_PATH", str(Path(__file__).resolve().parents[3] / "papers.db")))
DEFAULT_USER_ID = int(os.getenv("BUNKEN_DEFAULT_USER_ID", "1"))


def resolve_user_id() -> int:
    return DEFAULT_USER_ID


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def search_user_papers(user_id: int, query: str) -> list[PaperSummary]:
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
