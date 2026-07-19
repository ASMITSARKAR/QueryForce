import json
from src.rag.embedder import get_or_create_collection
from src.db.inspector import get_full_schema

async def route_relevant_schemas(user_query: str, top_k: int = 3) -> tuple[str, list[float]]:
    """
    Uses ChromaDB to perform semantic search and retrieve the most relevant tables.
    Implements the G1 Adaptive top_k with Foreign Key expansion fallback.
    """
    collection = get_or_create_collection()
    
    # 1. Perform initial top-K semantic search
    results = collection.query(
        query_texts=[user_query],
        n_results=top_k
    )
    
    if not results['ids'] or not results['ids'][0]:
        return "", []
        
    retrieved_table_names = set(results['ids'][0])
    
    # 2. G1 Fix: Adaptive FK-Expansion Fallback
    # If a retrieved table depends on another table via FK, bring that table in too!
    full_schema = await get_full_schema()
    
    expanded = True
    while expanded:
        expanded = False
        tables_to_add = set()
        
        for table_name in retrieved_table_names:
            if table_name in full_schema:
                for fk in full_schema[table_name]["foreign_keys"]:
                    fk_target = fk["table"]
                    if fk_target not in retrieved_table_names and fk_target not in tables_to_add:
                        tables_to_add.add(fk_target)
                        expanded = True
                        
        retrieved_table_names.update(tables_to_add)
        
    # 3. Build the final context block
    ddl_blocks = []
    # Fetch the DDL for all resolved tables
    for table_name in retrieved_table_names:
        if table_name in full_schema:
            ddl_blocks.append(f"-- Table: {table_name}\n{full_schema[table_name]['ddl']}")
            
    final_schema_context = "\n\n".join(ddl_blocks)
    
    # Cosine confidence scores (bounded 0-1 because of G3 hnsw:space=cosine)
    # Chroma returns distance. Confidence = 1 - distance.
    # We only have scores for the initially retrieved tables, not the FK-expanded ones.
    distances = results['distances'][0]
    confidence_scores = [max(0.0, 1.0 - d) for d in distances]
    
    return final_schema_context, confidence_scores

if __name__ == "__main__":
    import asyncio
    async def test():
        q = "Show me the top products purchased by customers in Canada"
        context, scores = await route_relevant_schemas(q)
        print(f"Confidence Scores (0-1): {scores}")
        print(f"\nConstructed Context sent to LLM:\n{context}")
    asyncio.run(test())
