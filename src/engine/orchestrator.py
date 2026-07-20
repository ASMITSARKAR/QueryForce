import time
from src.config import settings
from src.rag.rules import inject_business_rules
from src.rag.router import route_relevant_schemas
from src.engine.llm import generate_sql_only
from src.engine.validator import validate_and_format_sql
from src.db.executor import execute_readonly_query
from src.engine.errors import QueryExecutionError, SecurityViolationError
from src.db.telemetry import log_execution_metric

async def execute_pipeline_with_retry(user_question: str) -> dict:
    """
    Day 14: Encapsulates the entire intelligence pipeline and implements a retry loop
    for LLM syntax errors.
    """
    start_time = time.time()
    
    # 1. Rules Engine
    enriched_query = inject_business_rules(user_question)
    
    # 2. RAG Router
    schema_context, confidence_scores = await route_relevant_schemas(enriched_query)
    
    max_conf = max(confidence_scores) if confidence_scores else 0.0
    
    # Confidence filter
    if max_conf < 0.15:
        raise ValueError("Confidence too low. The question does not appear to be related to the database schema.")
        
    retry_context = ""
    last_error = None
    sql = None  # Track sql across attempts to avoid fragile locals() check
    
    # Retry Loop: 1 initial attempt + MAX_RETRIES retries
    max_attempts = settings.MAX_RETRIES + 1
    for attempt in range(max_attempts):
        try:
            # 3. LLM Generation
            sql = await generate_sql_only(enriched_query, schema_context, retry_context)
            
            # 4. AST Validation
            secure_sql = validate_and_format_sql(sql)
            
            # 5. Database Execution
            results_generator = execute_readonly_query(secure_sql)
            
            # Fetch the first chunk immediately to catch any execution errors inside the retry loop
            try:
                first_chunk = await anext(results_generator)
            except StopAsyncIteration:
                first_chunk = []
                
            async def streaming_results():
                if first_chunk:
                    yield first_chunk
                async for chunk in results_generator:
                    yield chunk
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Telemetry Log
            await log_execution_metric(
                prompt=user_question,
                sql=secure_sql,
                ast_status="CLEAN",
                retries=attempt,
                latency_ms=latency_ms,
                success=True
            )
            
            return {
                "sql": secure_sql,
                "results_stream": streaming_results(),
                "first_chunk": first_chunk,
                "latency_ms": latency_ms,
                "retries": attempt,
                "confidence": max_conf
            }
            
        except SecurityViolationError as e:
            # Never retry security violations (e.g. DROP TABLE attempts)
            latency_ms = (time.time() - start_time) * 1000
            await log_execution_metric(
                prompt=user_question,
                sql=sql,
                ast_status="BLOCKED",
                retries=attempt,
                latency_ms=latency_ms,
                success=False,
                error_trace=str(e)[:200]
            )
            raise
            
        except Exception as e:
            last_error = e
            retry_context = str(e)
            
    # Exhausted retries
    latency_ms = (time.time() - start_time) * 1000
    await log_execution_metric(
        prompt=user_question,
        sql=None,
        ast_status="ERROR",
        retries=settings.MAX_RETRIES,
        latency_ms=latency_ms,
        success=False,
        error_trace=str(last_error)[:200]
    )
    raise QueryExecutionError(f"Failed after {max_attempts} attempts ({settings.MAX_RETRIES} retries). Last error: {last_error}")
