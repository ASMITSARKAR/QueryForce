import re
from groq import AsyncGroq
from src.config import settings
from src.db.telemetry import log_execution_metric

# Initialize Groq client
# We use AsyncGroq since the pipeline is async
client = AsyncGroq(api_key=settings.GROQ_API_KEY.get_secret_value())

def extract_sql(raw_output: str) -> str:
    """
    G4 - Three-tier extraction strategy to prevent LLM chattiness from crashing the AST parser.
    """
    # Tier 1: Primary - Look for fenced code blocks
    fence_pattern = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
    match = fence_pattern.search(raw_output)
    if match:
        return match.group(1).strip()
        
    # Tier 2: Secondary - Look for SELECT or WITH
    # Find the first SELECT or WITH and capture up to the first semicolon or end
    keyword_pattern = re.compile(r"\b(SELECT|WITH)\b.*?(?:;|$)", re.IGNORECASE | re.DOTALL)
    match = keyword_pattern.search(raw_output)
    if match:
        return match.group(0).strip()
        
    # Tier 3: Fallback - Strip fences manually if they were malformed
    return re.sub(r"```(?:sql)?|```", "", raw_output).strip()

async def generate_sql_only(prompt: str, schema_context: str, retry_context: str = "") -> str:
    system_prompt = (
        "You are an expert SQLite SQL generator. "
        "Your only job is to write a syntactically correct SQLite query that answers the user's question based on the provided schema. "
        "Do NOT use MySQL, PostgreSQL, or SQL Server specific functions. Stick strictly to SQLite. "
        "Do NOT include any explanatory text before or after the SQL. "
        "Output ONLY the SQL code."
    )
    
    user_message = f"Schema:\n{schema_context}\n\nQuestion: {prompt}"
    
    if retry_context:
        # T10 Fix: Truncate error traceback to 200 characters to prevent context window explosion
        # Some SQL errors (like syntax errors on massive generated queries) can be thousands of characters long
        truncated_error = str(retry_context)[:200]
        user_message += f"\n\nPrevious attempt failed with:\n{truncated_error}...\nPlease correct the SQL."
        
    response = await client.chat.completions.create(
        model=settings.LLM_SQL_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0.0, # Zero temp for SQL generation to maximize determinism
        max_tokens=1024
    )
    
    raw_output = response.choices[0].message.content
    
    # If this was a retry, log the raw LLM response for debugging
    if retry_context:
        await log_execution_metric(
            prompt=f"[RETRY RAW] {prompt}",
            error_trace=raw_output[:500] # Log first 500 chars of raw output for debugging
        )
        
    return extract_sql(raw_output)

async def synthesize_results(prompt: str, sql: str, results: list[dict]) -> str:
    """
    Day 15: Translates raw tabular JSON results into a conversational answer.
    Uses the faster, cheaper 8b model for speed and efficiency.
    """
    system_prompt = (
        "You are a concise data analyst. The user asked a business question, and we ran a SQL query to get the answer. "
        "Your job is to translate the raw JSON results into a clear, natural language sentence. "
        "Do NOT mention the SQL query itself, do NOT say 'Based on the data', just give the direct answer."
    )
    
    # Cap result string length to prevent massive token burn on large tables
    results_str = str(results)[:2000] 
    
    user_message = f"User Question: {prompt}\n\nData Results:\n{results_str}"
    
    response = await client.chat.completions.create(
        model=settings.LLM_SYNTH_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0.3,
        max_tokens=256
    )
    
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    import asyncio
    async def test():
        schema = "CREATE TABLE users (id INTEGER, name TEXT);"
        q = "Count all users"
        sql = await generate_sql_only(q, schema)
        print(f"Generated SQL: {sql}")
    asyncio.run(test())
