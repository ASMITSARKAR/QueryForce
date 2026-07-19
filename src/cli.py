import os
import sys
import logging
import warnings

# ── Silence ChromaDB/Posthog telemetry warnings ──────────────────────────
# ChromaDB's posthog client uses print() directly to stderr, bypassing Python's
# logging system. We redirect stderr temporarily during import, then restore it.
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
logging.getLogger("chromadb").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
logging.getLogger("posthog").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore", message=".*telemetry.*")

# Monkey-patch posthog.capture to silently do nothing
try:
    import posthog
    posthog.capture = lambda *args, **kwargs: None
except ImportError:
    pass

import asyncio
import time
from tabulate import tabulate

from src.rag.rules import inject_business_rules
from src.rag.router import route_relevant_schemas
from src.engine.llm import generate_sql_only
from src.engine.validator import validate_and_format_sql
from src.db.executor import execute_readonly_query
from src.db.telemetry import log_execution_metric, init_telemetry_db
from src.engine.errors import QueryExecutionError, SecurityViolationError

# ANSI Color Codes for terminal UI
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
CYAN = "\033[96m"

def colorize_sql(sql: str) -> str:
    """Applies basic ANSI color coding to SQL keywords for better readability."""
    keywords_green = ["SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "LIMIT", "WITH", "AS"]
    keywords_yellow = ["JOIN", "INNER JOIN", "LEFT JOIN", "ON", "AND", "OR"]
    
    colored_sql = sql
    for kw in keywords_green:
        colored_sql = colored_sql.replace(kw, f"{GREEN}{kw}{RESET}")
    for kw in keywords_yellow:
        colored_sql = colored_sql.replace(kw, f"{YELLOW}{kw}{RESET}")
        
    return colored_sql

async def main_loop():
    # Ensure telemetry DB is initialized
    await init_telemetry_db()
    
    print(f"{CYAN}=========================================={RESET}")
    print(f"{CYAN}  QueryForce CLI (RAG Vector Router)      {RESET}")
    print(f"{CYAN}=========================================={RESET}")
    print("Initializing Vector Store RAG Router...")
    
    print(f"{GREEN}Ready! Type 'exit' to quit.{RESET}\n")
    
    while True:
        try:
            user_query = input(f"{CYAN}QueryForce > {RESET}")
            if user_query.lower() in ('exit', 'quit'):
                print("Goodbye!")
                break
            if not user_query.strip():
                continue
                
            start_time = time.time()
            
            try:
                # Execute the full pipeline (RAG -> Rules -> LLM -> Validation -> Execution -> Telemetry)
                result = await execute_pipeline_with_retry(user_query)
                
                print(f"{YELLOW}RAG Confidence: {result['confidence'] * 100:.1f}%{RESET}")
                
                if result['retries'] > 0:
                    print(f"{YELLOW}Warning: AI generated invalid SQL initially. Resolved after {result['retries']} retries.{RESET}")
                
                print(f"\n{colorize_sql(result['sql'])}\n")
                
                # Display Results
                if not result['results']:
                    print("Result: No rows returned.")
                else:
                    headers = result['results'][0].keys()
                    rows = [list(r.values()) for r in result['results']]
                    print(tabulate(rows, headers=headers, tablefmt="pretty"))
                    
                print(f"\n{CYAN}Execution Time: {result['latency_ms']:.0f} ms{RESET}\n")
                
            except ValueError as e:
                # Confidence threshold rejected
                print(f"\n{RED}{e}{RESET}\n")
            except QueryExecutionError as e:
                print(f"\n{RED}Execution Error: {e}{RESET}\n")
            except SecurityViolationError as e:
                print(f"\n{RED}Security Blocked: {e}{RESET}\n")
            except Exception as e:
                print(f"\n{RED}Unexpected Error: {e}{RESET}\n")

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nExiting...")
