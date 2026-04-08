"""Tool: database_query"""

def query_db(db_path: str, sql: str, params: tuple = ()) -> list:
    """Execute a read-only SQL query on a SQLite database."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

