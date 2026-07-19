import uuid
import aiosqlite
from pathlib import Path
from src.config import settings

async def get_connection():
    db_path = Path(settings.TELEMETRY_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = await aiosqlite.connect(db_path)
    # T3 Fix: Enable WAL mode for concurrent SSE streams to prevent DB locking
    await conn.execute("PRAGMA journal_mode = WAL;")
    await conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

async def init_telemetry_db():
    conn = await get_connection()
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS execution_logs (
        id TEXT PRIMARY KEY,
        prompt TEXT,
        sql TEXT,
        ast_status TEXT,
        retries INTEGER,
        latency_ms REAL,
        success BOOLEAN,
        error_trace TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    await conn.commit()
    await conn.close()

async def log_execution_metric(
    prompt: str, 
    sql: str | None = None, 
    ast_status: str = "CLEAN", 
    retries: int = 0, 
    latency_ms: float = 0.0, 
    success: bool = True, 
    error_trace: str | None = None
) -> str:
    conn = await get_connection()
    log_id = str(uuid.uuid4())
    await conn.execute("""
    INSERT INTO execution_logs (id, prompt, sql, ast_status, retries, latency_ms, success, error_trace)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (log_id, prompt, sql, ast_status, retries, latency_ms, success, error_trace))
    await conn.commit()
    await conn.close()
    return log_id

async def get_recent_logs(limit: int = 20) -> list[dict]:
    conn = await get_connection()
    conn.row_factory = aiosqlite.Row
    cursor = await conn.execute("""
        SELECT id, prompt, sql, ast_status, retries, latency_ms, success, error_trace, created_at
        FROM execution_logs
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = await cursor.fetchall()
    await conn.close()
    return [dict(row) for row in rows]

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_telemetry_db())
    print("Telemetry database initialized.")
