import asyncio
import aiosqlite
from pathlib import Path
from src.config import settings
from src.engine.errors import QueryExecutionError

async def execute_readonly_query(sql: str):
    """
    Executes a SQL query against the analytics database in strict read-only mode.
    Yields results as chunks to prevent memory exhaustion and allows streaming to the frontend.
    """
    db_uri = f"file:{Path(settings.ANALYTICS_DB_PATH).absolute().as_posix()}?mode=ro"
    
    try:
        async with aiosqlite.connect(db_uri, uri=True) as db:
            db.row_factory = aiosqlite.Row
            
            # Pre-Execution Cost Estimation (Algorithmic DoS Prevention)
            explain_cursor = await db.execute(f"EXPLAIN QUERY PLAN {sql}")
            plan_rows = await explain_cursor.fetchall()
            scan_count = sum(1 for row in plan_rows if "SCAN" in str(row[3]) or "SCAN TABLE" in str(row[3]))
            if scan_count > 1:
                # Multiple full table scans implies an unindexed cartesian product or nested loop
                raise QueryExecutionError("Query rejected: Algorithmic Denial of Service detected (multiple full table scans without indexes).")
            
            # Execute with Hard Timeout and Chunked Streaming
            try:
                # We start the execution with a 3.0 second timeout to prevent CPU lockup
                cursor = await asyncio.wait_for(db.execute(sql), timeout=3.0)
                
                # Fetch results in chunks of 100 rows to prevent unbounded memory exhaustion
                while True:
                    rows = await cursor.fetchmany(100)
                    if not rows:
                        break
                    yield [dict(row) for row in rows]
                    
            except asyncio.TimeoutError:
                # Immediately sever the C-thread executing the combinatorial explosion
                db._conn.interrupt()
                raise QueryExecutionError("Query exceeded 3-second execution limit (Cartesian explosion blocked).")
                
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
