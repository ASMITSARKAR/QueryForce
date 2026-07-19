import asyncio
import sqlite3
from pathlib import Path
from tabulate import tabulate
import sys

# Ensure we can import src when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.db.inspector import get_full_schema
from src.rag.embedder import get_or_create_collection

async def ingest_schema_catalog():
    print("Starting schema catalog ingestion...")
    
    # 1. Connect to ChromaDB
    collection = get_or_create_collection()
    
    # 2. Fetch base schema from the inspector
    schema = await get_full_schema()
    
    # 3. Connect to SQLite to grab sample rows
    db_path = Path(settings.ANALYTICS_DB_PATH).absolute()
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    ids = []
    documents = []
    metadatas = []
    summary_data = []
    
    for table_name, data in schema.items():
        # Get column names and sample rows
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        rows = cursor.fetchall()
        
        # If there are no rows, columns are still available via PRAGMA
        if rows:
            cols = list(rows[0].keys())
        else:
            col_cursor = conn.execute(f"PRAGMA table_info({table_name})")
            cols = [c[1] for c in col_cursor.fetchall()]
            
        sample_data = [dict(row) for row in rows]
            
        # Format Foreign Keys
        fks_str = "None"
        if data["foreign_keys"]:
            fks_str = ", ".join([f"{fk['from']} -> {fk['table']}.{fk['to']}" for fk in data["foreign_keys"]])
            
        # Build the dense semantic document
        doc = (
            f"Table: {table_name} | "
            f"Columns: {', '.join(cols)} | "
            f"Foreign Keys: {fks_str} | "
            f"Sample Data (top 3 rows): {sample_data}"
        )
        
        ids.append(table_name)
        documents.append(doc)
        metadatas.append({"ddl": data["ddl"]})
        
        summary_data.append([table_name, len(doc), len(data["ddl"])])
        
    conn.close()
    
    print(f"Upserting {len(ids)} tables into ChromaDB...")
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    
    print("\nIngestion Complete! Summary:")
    print(tabulate(summary_data, headers=["Table ID", "Doc Char Count", "DDL Char Count"], tablefmt="pretty"))

if __name__ == "__main__":
    asyncio.run(ingest_schema_catalog())
