import os
import sqlite3

# --- ANCHOR PATHING ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
DB_PATH = os.path.join(PROCESSED_DATA_DIR, "processed_data.db")


def get_db_path():
    return DB_PATH


def _connect():
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = _connect()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            mtime REAL,
            size INTEGER,
            content_hash TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            path TEXT NOT NULL,
            source TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT,
            chunk_hash TEXT,
            PRIMARY KEY (path, chunk_index)
        )
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(chunk_hash)")

    c.execute("""
        CREATE TABLE IF NOT EXISTS crawl_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            changed INTEGER NOT NULL DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS vector_cache (
            chunk_hash TEXT PRIMARY KEY,
            vector BLOB NOT NULL,
            dim INTEGER NOT NULL,
            dtype TEXT NOT NULL
        )
    """)

    c.execute("INSERT OR IGNORE INTO crawl_state (id, changed) VALUES (1, 0)")
    conn.commit()
    conn.close()


def load_manifest():
    init_db()
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT path, name, mtime, size, content_hash FROM files")
    rows = c.fetchall()
    conn.close()

    files = {}
    for path, name, mtime, size, content_hash in rows:
        files[path] = {
            "path": path,
            "name": name,
            "mtime": mtime,
            "size": size,
            "content_hash": content_hash
        }
    return {"files": files}


def save_manifest(manifest):
    init_db()
    files = manifest.get("files", {})
    conn = _connect()
    c = conn.cursor()

    if files:
        c.execute("SELECT path FROM files")
        existing_paths = {row[0] for row in c.fetchall()}
        new_paths = set(files.keys())
        paths_to_delete = [path for path in existing_paths if path not in new_paths]

        entries = []
        for path, entry in files.items():
            entries.append((
                path,
                entry.get("name"),
                entry.get("mtime"),
                entry.get("size"),
                entry.get("content_hash")
            ))

        c.executemany("""
            INSERT INTO files (path, name, mtime, size, content_hash)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                name = excluded.name,
                mtime = excluded.mtime,
                size = excluded.size,
                content_hash = excluded.content_hash
        """, entries)
        if paths_to_delete:
            batch_size = 500
            for i in range(0, len(paths_to_delete), batch_size):
                batch = paths_to_delete[i:i + batch_size]
                placeholders = ",".join(["?"] * len(batch))
                c.execute(f"DELETE FROM files WHERE path IN ({placeholders})", batch)
                c.execute(f"DELETE FROM chunks WHERE path IN ({placeholders})", batch)
    else:
        c.execute("DELETE FROM files")
        c.execute("DELETE FROM chunks")

    conn.commit()
    conn.close()


def save_chunks_for_file(filepath, chunk_records):
    init_db()
    conn = _connect()
    c = conn.cursor()
    c.execute("DELETE FROM chunks WHERE path = ?", (filepath,))

    if chunk_records:
        rows = []
        for record in chunk_records:
            rows.append((
                record.get("path"),
                record.get("source"),
                record.get("chunk_index"),
                record.get("content"),
                record.get("chunk_hash")
            ))
        c.executemany("""
            INSERT INTO chunks (path, source, chunk_index, content, chunk_hash)
            VALUES (?, ?, ?, ?, ?)
        """, rows)

    conn.commit()
    conn.close()


def delete_chunks_for_file(filepath):
    init_db()
    conn = _connect()
    c = conn.cursor()
    c.execute("DELETE FROM chunks WHERE path = ?", (filepath,))
    conn.commit()
    conn.close()


def get_all_chunks():
    init_db()
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        SELECT source, path, chunk_index, content, chunk_hash
        FROM chunks
        ORDER BY path, chunk_index
    """)
    rows = c.fetchall()
    conn.close()

    chunks = []
    for source, path, chunk_index, content, chunk_hash in rows:
        chunks.append({
            "source": source,
            "path": path,
            "chunk_index": chunk_index,
            "content": content,
            "chunk_hash": chunk_hash
        })
    return chunks


def get_chunk_count():
    init_db()
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM chunks")
    count = c.fetchone()[0]
    conn.close()
    return count


def save_crawl_state(changed):
    init_db()
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        UPDATE crawl_state
        SET changed = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (1 if changed else 0,))
    conn.commit()
    conn.close()


def get_crawl_state():
    init_db()
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT changed FROM crawl_state WHERE id = 1")
    row = c.fetchone()
    conn.close()
    if row is None:
        return None
    return bool(row[0])


def load_vector_cache_rows():
    init_db()
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT chunk_hash, vector, dim, dtype FROM vector_cache")
    rows = c.fetchall()
    conn.close()
    return rows


def upsert_vector_cache_rows(rows):
    if not rows:
        return
    init_db()
    conn = _connect()
    c = conn.cursor()
    c.executemany("""
        INSERT INTO vector_cache (chunk_hash, vector, dim, dtype)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chunk_hash) DO UPDATE SET
            vector = excluded.vector,
            dim = excluded.dim,
            dtype = excluded.dtype
    """, rows)
    conn.commit()
    conn.close()
