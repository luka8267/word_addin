import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).with_name("papers.db")


def main() -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    existing = cursor.execute(
        """
        SELECT id
        FROM papers
        WHERE user_id = ?
          AND title = ?
        LIMIT 1
        """,
        (1, "Sample Clinical Reasoning Paper"),
    ).fetchone()

    if existing:
        print("sample paper already exists")
        return

    max_order = cursor.execute(
        "SELECT COALESCE(MAX(display_order), 0) FROM papers WHERE user_id = ?",
        (1,),
    ).fetchone()[0]

    cursor.execute(
        """
        INSERT INTO papers (title, authors, journal, year, pdf_path, user_id, display_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Sample Clinical Reasoning Paper",
            "Suzuki, Sato",
            "Bunken Demo Journal",
            2024,
            None,
            1,
            max_order + 1,
        ),
    )
    connection.commit()
    print("sample paper inserted")


if __name__ == "__main__":
    main()
