import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


class IndexMismatch(ValueError):
    pass


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "labkb.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL, chunk_count INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    text TEXT NOT NULL, location TEXT NOT NULL, vector TEXT);
                CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA secure_delete=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def check_fingerprint(self, fingerprint: str):
        with self.connect() as db:
            row = db.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
            if row and row[0] != fingerprint:
                raise IndexMismatch(
                    "索引配置或 embedding 模型已变化；请使用新的 LABKB_DATA_DIR 重新导入，或删除全部文档后重试"
                )

    def list_documents(self):
        with self.connect() as db:
            return [
                dict(row) for row in db.execute("SELECT * FROM documents ORDER BY created_at DESC")
            ]

    def find_hash(self, sha256):
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE sha256=?", (sha256,)).fetchone()
            return dict(row) if row else None

    def insert(self, name, sha256, chunks, fingerprint, max_chunks):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT * FROM documents WHERE sha256=?", (sha256,)).fetchone()
            if previous:
                return dict(previous), True
            current = db.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
            if current and current[0] != fingerprint:
                raise IndexMismatch("索引配置已变化，请使用新的数据目录重新导入")
            count = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            if count + len(chunks) > max_chunks:
                raise ValueError(f"原型最多支持 {max_chunks} 个文本块，请缩小语料或升级检索后端")
            dimensions = {len(c["vector"]) for c in chunks if c.get("vector")}
            if len(dimensions) > 1:
                raise IndexMismatch("入库向量维度不一致")
            dimension = str(next(iter(dimensions))) if dimensions else "none"
            old_dimension = db.execute(
                "SELECT value FROM metadata WHERE key='dimension'"
            ).fetchone()
            if old_dimension and old_dimension[0] != dimension:
                raise IndexMismatch("向量维度与已有索引不一致，入库已取消")
            document = {
                "id": uuid.uuid4().hex,
                "name": name,
                "sha256": sha256,
                "created_at": datetime.now(UTC).isoformat(),
                "chunk_count": len(chunks),
            }
            db.execute(
                "INSERT INTO documents VALUES (:id,:name,:sha256,:created_at,:chunk_count)",
                document,
            )
            db.executemany(
                "INSERT INTO chunks(document_id,text,location,vector) VALUES (?,?,?,?)",
                [
                    (
                        document["id"],
                        c["text"],
                        c["location"],
                        json.dumps(c["vector"]) if c.get("vector") else None,
                    )
                    for c in chunks
                ],
            )
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('fingerprint',?)", (fingerprint,))
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('dimension',?)", (dimension,))
            return document, False

    def all_chunks(self):
        with self.connect() as db:
            rows = db.execute(
                "SELECT c.*,d.name AS document_name FROM chunks c JOIN documents d ON c.document_id=d.id"
            ).fetchall()
        return [
            {**dict(r), "vector": json.loads(r["vector"]) if r["vector"] else None} for r in rows
        ]

    def delete(self, document_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            removed = db.execute("DELETE FROM documents WHERE id=?", (document_id,)).rowcount
            if not db.execute("SELECT 1 FROM documents LIMIT 1").fetchone():
                db.execute("DELETE FROM metadata WHERE key IN ('fingerprint','dimension')")
            return bool(removed)
