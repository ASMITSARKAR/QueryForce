import asyncio
import aiosqlite
from pathlib import Path
from src.config import settings
from src.engine.errors import QueryExecutionError

async def execute_readonly_query(sql: str) -> list[dict]:
    """
    Executes a SQL query against the analytics database in strict read-only mode.
    Returns a list of dictionaries mapping column names to values.
    """
    # T6 fix: Explicit uri=True required. Without it, SQLite creates a literal file named 'file:...'
    db_uri = f"file:{Path(settings.ANALYTICS_DB_PATH).absolute().as_posix()}?mode=ro"
    
    try:
        async with aiosqlite.connect(db_uri, uri=True) as db:
            db.row_factory = aiosqlite.Row
            
            # G5 fix: Execution timeout (10 seconds)
            # A query could be read-only but still stall the DB (e.g., massive cross-joins)
            cursor = await asyncio.wait_for(db.execute(sql), timeout=10.0)
            rows = await cursor.fetchall()
            
            return [dict(row) for row in rows]
            
    except asyncio.TimeoutError:
        raise QueryExecutionError("Query exceeded 10-second limit (possible accidental cross-join or infinite recursion).")
    except aiosqlite.OperationalError as e:
        raise QueryExecutionError(str(e))
    except aiosqlite.DatabaseError as e:
        raise QueryExecutionError(str(e))

if __name__ == "__main__":
    async def test():
        print("Testing valid query...")
        try:
            res = await execute_readonly_query("SELECT name, country FROM customers LIMIT 2")
            print("Success:", res)
        except Exception as e:
            print("Failed:", e)
            
        print("\nTesting read-only enforcement (DROP TABLE)...")
        try:
            await execute_readonly_query("DROP TABLE customers")
        except Exception as e:
            print("Blocked (as expected):", e)
            
    asyncio.run(test())
