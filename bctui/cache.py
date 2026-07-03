from collections.abc import Sequence
from pathlib import Path
import xdg.BaseDirectory
import sqlite3
from bctui.bandcamp import CollectionEntry


def save_collection(collection: Sequence[CollectionEntry]) -> None:
    cache_dir = Path(xdg.BaseDirectory.save_cache_path("bctui"))
    con = sqlite3.connect(cache_dir / "collection.db")

    try:
        cur = con.cursor()
        cur.execute("DROP TABLE IF EXISTS collection")
        cur.execute("CREATE TABLE collection(uid, artist, title, url)")

        cur.executemany(
            "INSERT INTO collection VALUES (:uid, :artist, :title, :url)",
            [e.__dict__ for e in collection],
        )
    finally:
        con.commit()
        con.close()


def load_collection() -> list[CollectionEntry]:
    cache_dir = Path(xdg.BaseDirectory.save_cache_path("bctui"))
    con = sqlite3.connect(cache_dir / "collection.db")

    try:
        cur = con.cursor()
        table_exists = (
            cur.execute(
                """
            SELECT count(*) FROM sqlite_master
            WHERE type='table' AND name='collection'
             """
            ).fetchall()[0][0]
            == 1
        )

        if not table_exists:
            return []

        rows = cur.execute("SELECT * FROM collection").fetchall()
        return [CollectionEntry(*row) for row in rows]
    finally:
        con.commit()
        con.close()
