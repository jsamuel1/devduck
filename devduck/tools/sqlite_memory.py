"""🧠 SQLite-based persistent memory for DevDuck.

Full-text search, tagging, metadata, import/export, raw SQL.
Each DevDuck instance gets its own persistent memory database.

Examples:
    sqlite_memory(action="store", content="Important finding about X", title="Research", tags=["research", "x"])
    sqlite_memory(action="search", query="important finding")
    sqlite_memory(action="list", limit=5)
    sqlite_memory(action="get", memory_id="mem_abc123")
    sqlite_memory(action="stats")
    sqlite_memory(action="sql", sql_query="SELECT COUNT(*) FROM memories")
    sqlite_memory(action="export", export_format="json")
"""

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from strands import tool


def _get_db_path(db_path: Optional[str] = None) -> str:
    path = db_path or os.path.expanduser("~/.devduck/sqlite_memory.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _init_db(conn: sqlite3.Connection):
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            title TEXT,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            tags TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            word_count INTEGER,
            char_count INTEGER
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            id UNINDEXED, title, content, tags,
            content='memories', content_rowid='rowid'
        );
        CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, id, title, content, tags)
            VALUES (new.rowid, new.id, new.title, new.content, new.tags);
        END;
        CREATE TRIGGER IF NOT EXISTS mem_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, id, title, content, tags)
            VALUES ('delete', old.rowid, old.id, old.title, old.content, old.tags);
        END;
        CREATE TRIGGER IF NOT EXISTS mem_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, id, title, content, tags)
            VALUES ('delete', old.rowid, old.id, old.title, old.content, old.tags);
            INSERT INTO memories_fts(rowid, id, title, content, tags)
            VALUES (new.rowid, new.id, new.title, new.content, new.tags);
        END;
        CREATE TABLE IF NOT EXISTS tags (
            name TEXT PRIMARY KEY, count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()


@tool
def sqlite_memory(
    action: str,
    content: Optional[str] = None,
    title: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    memory_id: Optional[str] = None,
    query: Optional[str] = None,
    sql_query: Optional[str] = None,
    search_type: str = "fulltext",
    limit: int = 50,
    offset: int = 0,
    order_by: str = "created_at DESC",
    filters: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
    export_format: str = "json",
    backup_path: Optional[str] = None,
) -> Dict[str, Any]:
    """🧠 SQLite-based persistent memory with full-text search.

    Args:
        action: store, search, list, get, delete, update, stats, export, import_data, backup, optimize, sql
        content: Text content (for store/update)
        title: Title/summary
        tags: Tags for categorization
        metadata: Additional key-value metadata
        memory_id: Memory ID (for get/delete/update)
        query: Search query (for search)
        sql_query: Raw SQL (for sql action)
        search_type: fulltext, exact, or fuzzy
        limit: Max results (default: 50)
        offset: Pagination offset
        order_by: SQL ORDER BY clause
        filters: Additional filters {tags, created_after, created_before}
        db_path: Custom database path
        export_format: json, csv, or sql
        backup_path: Path for backup/export

    Returns:
        Dict with status and content
    """
    try:
        conn = sqlite3.connect(_get_db_path(db_path))
        conn.row_factory = sqlite3.Row
        _init_db(conn)

        if action == "store":
            if not content:
                return {"status": "error", "content": [{"text": "content required"}]}

            mid = memory_id or f"mem_{uuid.uuid4().hex[:12]}"
            chash = hashlib.sha256(content.encode()).hexdigest()

            # Dedup check
            row = conn.execute(
                "SELECT id FROM memories WHERE content_hash=?", (chash,)
            ).fetchone()
            if row:
                return {
                    "status": "success",
                    "content": [{"text": f"⚠️ Duplicate exists: {row['id']}"}],
                }

            auto_title = title or (
                content[:500].strip() + ("..." if len(content) > 500 else "")
            )
            wc, cc = len(content.split()), len(content)
            tags_json = json.dumps(tags or [])
            meta_json = json.dumps(metadata or {})

            conn.execute(
                "INSERT INTO memories (id,title,content,content_hash,tags,metadata,word_count,char_count) VALUES (?,?,?,?,?,?,?,?)",
                (mid, auto_title, content, chash, tags_json, meta_json, wc, cc),
            )
            for t in tags or []:
                conn.execute(
                    "INSERT INTO tags (name,count) VALUES (?,1) ON CONFLICT(name) DO UPDATE SET count=count+1",
                    (t,),
                )
            conn.commit()

            return {
                "status": "success",
                "content": [
                    {
                        "text": f"✅ Stored '{auto_title}' ({mid}) - {wc} words, tags: {', '.join(tags or [])}"
                    }
                ],
            }

        elif action in ("search", "retrieve"):
            if not query:
                return {"status": "error", "content": [{"text": "query required"}]}

            if search_type == "fulltext":
                rows = conn.execute(
                    "SELECT m.* FROM memories_fts f JOIN memories m ON m.id=f.id WHERE memories_fts MATCH ? LIMIT ? OFFSET ?",
                    (query, limit, offset),
                ).fetchall()
            elif search_type == "exact":
                term = f"%{query}%"
                rows = conn.execute(
                    f"SELECT * FROM memories WHERE content LIKE ? OR title LIKE ? ORDER BY {order_by} LIMIT ? OFFSET ?",
                    (term, term, limit, offset),
                ).fetchall()
            else:  # fuzzy
                words = query.split()
                clauses = []
                params = []
                for w in words:
                    clauses.append("(content LIKE ? OR title LIKE ?)")
                    params.extend([f"%{w}%", f"%{w}%"])
                rows = conn.execute(
                    f"SELECT * FROM memories WHERE {' OR '.join(clauses)} ORDER BY {order_by} LIMIT ? OFFSET ?",
                    params + [limit, offset],
                ).fetchall()

            if not rows:
                return {
                    "status": "success",
                    "content": [{"text": f"No results for '{query}'"}],
                }

            lines = [f"🔍 Found {len(rows)} memories for '{query}':\n"]
            for i, r in enumerate(rows, 1):
                t = json.loads(r["tags"]) if r["tags"] else []
                preview = r["content"][:50000] + (
                    "..." if len(r["content"]) > 50000 else ""
                )
                lines.append(
                    f"{i}. **{r['title']}** (`{r['id']}`) - {r['word_count']}w, tags: {', '.join(t)}\n   {preview}\n"
                )

            return {"status": "success", "content": [{"text": "\n".join(lines)}]}

        elif action == "list":
            rows = conn.execute(
                f"SELECT * FROM memories ORDER BY {order_by} LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

            if not rows:
                return {
                    "status": "success",
                    "content": [{"text": "No memories stored."}],
                }

            lines = [f"📚 Memories ({len(rows)} of {total}):\n"]
            for i, r in enumerate(rows, offset + 1):
                t = json.loads(r["tags"]) if r["tags"] else []
                preview = r["content"][:200] + (
                    "..." if len(r["content"]) > 200 else ""
                )
                lines.append(
                    f"  {i}. {r['title']} (`{r['id']}`) - {r['word_count']}w, {', '.join(t)}\n     {preview}"
                )

            return {"status": "success", "content": [{"text": "\n".join(lines)}]}

        elif action == "get":
            if not memory_id:
                return {"status": "error", "content": [{"text": "memory_id required"}]}
            r = conn.execute(
                "SELECT * FROM memories WHERE id=?", (memory_id,)
            ).fetchone()
            if not r:
                return {
                    "status": "error",
                    "content": [{"text": f"Not found: {memory_id}"}],
                }
            t = json.loads(r["tags"]) if r["tags"] else []
            meta = json.loads(r["metadata"]) if r["metadata"] else {}
            text = f"📄 **{r['title']}** (`{r['id']}`)\n📅 {r['created_at']} | {r['word_count']}w\n🏷️ {', '.join(t)}\n"
            if meta:
                text += f"🔧 Metadata: {json.dumps(meta)}\n"
            text += f"\n{r['content']}"
            return {"status": "success", "content": [{"text": text}]}

        elif action == "delete":
            if not memory_id:
                return {"status": "error", "content": [{"text": "memory_id required"}]}
            r = conn.execute(
                "SELECT title,tags FROM memories WHERE id=?", (memory_id,)
            ).fetchone()
            if not r:
                return {
                    "status": "error",
                    "content": [{"text": f"Not found: {memory_id}"}],
                }
            for t in json.loads(r["tags"] or "[]"):
                conn.execute("UPDATE tags SET count=count-1 WHERE name=?", (t,))
            conn.execute("DELETE FROM tags WHERE count<=0")
            conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            conn.commit()
            return {
                "status": "success",
                "content": [{"text": f"✅ Deleted: {r['title']} ({memory_id})"}],
            }

        elif action == "update":
            if not memory_id:
                return {"status": "error", "content": [{"text": "memory_id required"}]}
            existing = conn.execute(
                "SELECT * FROM memories WHERE id=?", (memory_id,)
            ).fetchone()
            if not existing:
                return {
                    "status": "error",
                    "content": [{"text": f"Not found: {memory_id}"}],
                }

            updates, params = [], []
            if content is not None:
                updates.extend(
                    ["content=?", "content_hash=?", "word_count=?", "char_count=?"]
                )
                params.extend(
                    [
                        content,
                        hashlib.sha256(content.encode()).hexdigest(),
                        len(content.split()),
                        len(content),
                    ]
                )
            if title is not None:
                updates.append("title=?")
                params.append(title)
            if tags is not None:
                updates.append("tags=?")
                params.append(json.dumps(tags))
            if metadata is not None:
                updates.append("metadata=?")
                params.append(json.dumps(metadata))
            if not updates:
                return {"status": "success", "content": [{"text": "Nothing to update"}]}

            updates.append("updated_at=CURRENT_TIMESTAMP")
            params.append(memory_id)
            conn.execute(f"UPDATE memories SET {','.join(updates)} WHERE id=?", params)
            conn.commit()
            return {
                "status": "success",
                "content": [{"text": f"✅ Updated: {memory_id}"}],
            }

        elif action == "stats":
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            tag_count = conn.execute(
                "SELECT COUNT(*) FROM tags WHERE count>0"
            ).fetchone()[0]
            stats = conn.execute(
                "SELECT SUM(word_count) as tw, SUM(char_count) as tc, AVG(word_count) as aw FROM memories"
            ).fetchone()
            recent = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE created_at>=date('now','-7 days')"
            ).fetchone()[0]
            top_tags = conn.execute(
                "SELECT name,count FROM tags ORDER BY count DESC LIMIT 10"
            ).fetchall()

            text = f"📊 Memory Stats:\n  Total: {total} | Tags: {tag_count} | Recent (7d): {recent}\n"
            if total > 0:
                text += (
                    f"  Words: {stats['tw'] or 0:,} total, {stats['aw'] or 0:.0f} avg\n"
                )
            if top_tags:
                text += "  Top tags: " + ", ".join(
                    f"{t['name']}({t['count']})" for t in top_tags
                )
            return {"status": "success", "content": [{"text": text}]}

        elif action == "export":
            rows = conn.execute("SELECT * FROM memories").fetchall()
            if not rows:
                return {"status": "success", "content": [{"text": "Nothing to export"}]}

            memories = []
            for r in rows:
                m = dict(r)
                m["tags"] = json.loads(m["tags"]) if m["tags"] else []
                m["metadata"] = json.loads(m["metadata"]) if m["metadata"] else {}
                memories.append(m)

            if not backup_path:
                backup_path = f"/tmp/devduck/sqlite_memory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}"
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)

            if export_format == "json":
                with open(backup_path, "w") as f:
                    json.dump(memories, f, indent=2, default=str)
            elif export_format == "csv":
                import csv

                with open(backup_path, "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=memories[0].keys())
                    w.writeheader()
                    for m in memories:
                        m["tags"] = ",".join(m["tags"])
                        m["metadata"] = json.dumps(m["metadata"])
                        w.writerow(m)

            return {
                "status": "success",
                "content": [
                    {"text": f"✅ Exported {len(memories)} memories to {backup_path}"}
                ],
            }

        elif action == "import_data":
            if not backup_path or not os.path.exists(backup_path):
                return {
                    "status": "error",
                    "content": [{"text": f"File not found: {backup_path}"}],
                }
            with open(backup_path) as f:
                memories = json.load(f)
            imported, skipped = 0, 0
            for m in memories:
                if conn.execute(
                    "SELECT id FROM memories WHERE id=?", (m["id"],)
                ).fetchone():
                    skipped += 1
                    continue
                conn.execute(
                    "INSERT INTO memories (id,title,content,content_hash,tags,metadata,created_at,updated_at,word_count,char_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        m["id"],
                        m["title"],
                        m["content"],
                        m["content_hash"],
                        json.dumps(m["tags"]),
                        json.dumps(m["metadata"]),
                        m["created_at"],
                        m["updated_at"],
                        m["word_count"],
                        m["char_count"],
                    ),
                )
                for t in m["tags"]:
                    conn.execute(
                        "INSERT INTO tags (name,count) VALUES (?,1) ON CONFLICT(name) DO UPDATE SET count=count+1",
                        (t,),
                    )
                imported += 1
            conn.commit()
            return {
                "status": "success",
                "content": [{"text": f"✅ Imported {imported}, skipped {skipped}"}],
            }

        elif action == "backup":
            import shutil

            bp = (
                backup_path
                or f"/tmp/devduck/sqlite_memory_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            )
            os.makedirs(os.path.dirname(bp), exist_ok=True)
            shutil.copy2(_get_db_path(db_path), bp)
            return {"status": "success", "content": [{"text": f"✅ Backup: {bp}"}]}

        elif action == "optimize":
            conn.executescript(
                "ANALYZE; INSERT INTO memories_fts(memories_fts) VALUES('rebuild'); VACUUM; PRAGMA optimize;"
            )
            return {
                "status": "success",
                "content": [
                    {"text": "✅ Database optimized (analyzed, FTS rebuilt, vacuumed)"}
                ],
            }

        elif action == "sql":
            if not sql_query:
                return {"status": "error", "content": [{"text": "sql_query required"}]}
            c = conn.execute(sql_query)
            upper = sql_query.strip().upper()
            if upper.startswith(("SELECT", "WITH", "PRAGMA", "EXPLAIN")):
                rows = c.fetchall()
                if not rows:
                    return {
                        "status": "success",
                        "content": [{"text": "Query OK, no results."}],
                    }
                cols = [d[0] for d in c.description] if c.description else []
                lines = [" | ".join(cols)]
                for r in rows[:500]:
                    lines.append(
                        " | ".join(
                            str(v)[:1000] if v is not None else "NULL" for v in r
                        )
                    )
                return {
                    "status": "success",
                    "content": [
                        {"text": f"Results ({len(rows)} rows):\n" + "\n".join(lines)}
                    ],
                }
            else:
                conn.commit()
                return {
                    "status": "success",
                    "content": [
                        {
                            "text": f"✅ {sql_query.split()[0]} OK, {c.rowcount} rows affected"
                        }
                    ],
                }

        else:
            return {
                "status": "error",
                "content": [{"text": f"Unknown action: {action}"}],
            }

    except Exception as e:
        return {"status": "error", "content": [{"text": f"Error: {e}"}]}
    finally:
        if "conn" in locals():
            conn.close()
