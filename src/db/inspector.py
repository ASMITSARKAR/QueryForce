import aiosqlite
from pathlib import Path
from src.config import settings

async def get_connection():
    # T6 fix: Explicit uri=True required when passing file URIs
    db_uri = f"file:{Path(settings.ANALYTICS_DB_PATH).absolute().as_posix()}?mode=ro"
    return await aiosqlite.connect(db_uri, uri=True)

async def get_full_schema() -> dict[str, dict]:
    conn = await get_connection()
    try:
        conn.row_factory = aiosqlite.Row
        
        # Get all tables
        cursor = await conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = await cursor.fetchall()
        
        schema = {}
        for table in tables:
            table_name = table["name"]
            ddl = table["sql"]
            
            # Get foreign keys
            fk_cursor = await conn.execute(f"PRAGMA foreign_key_list({table_name})")
            fks = await fk_cursor.fetchall()
            
            schema[table_name] = {
                "ddl": ddl,
                "foreign_keys": [dict(fk) for fk in fks]
            }
    finally:
        await conn.close()
        
    return schema

async def format_schema_markdown() -> str:
    schema = await get_full_schema()
    lines = ["# Database Schema\n"]
    
    for table_name, data in schema.items():
        lines.append(f"## Table: `{table_name}`")
        lines.append("```sql")
        lines.append(data["ddl"])
        lines.append("```")
        if data["foreign_keys"]:
            lines.append("**Foreign Keys:**")
            for fk in data["foreign_keys"]:
                lines.append(f"- `{fk['from']}` -> `{fk['table']}.{fk['to']}`")
        lines.append("")
        
    return "\n".join(lines)

if __name__ == "__main__":
    import asyncio
    async def test():
        md = await format_schema_markdown()
        print(md)
    asyncio.run(test())
