from src.utils import suppress_chromadb_telemetry
suppress_chromadb_telemetry()

import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chromadb
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.db.inspector import get_connection
from src.db.telemetry import get_recent_logs, init_telemetry_db
from src.engine.orchestrator import execute_pipeline_with_retry
from src.engine.llm import synthesize_results
from src.api.auth import verify_api_key
from src.engine.errors import QueryExecutionError, SecurityViolationError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize required resources on startup."""
    await init_telemetry_db()
    yield


app = FastAPI(
    title="QueryForce API", 
    description="FastAPI Backend for QueryForce AI Analytics Engine",
    version="1.0.0",
    lifespan=lifespan
)

# G6: Apply rate limiter to protect Groq API quota
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allow CORS for the frontend web application
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the static UI directory (exempt from auth guard)
app.mount("/ui", StaticFiles(directory="ui"), name="ui")

@app.get("/")
async def serve_ui():
    return FileResponse("ui/index.html")

class QueryRequest(BaseModel):
    query: str

async def stream_generator(user_query: str):
    """
    Day 16: Server-Sent Events (SSE) generator.
    Yields JSON events piece-by-piece so the UI can show live progress.
    """
    try:
        # Event 1: Status (Routing)
        yield f"event: status\ndata: {json.dumps({'step': 'router', 'msg': 'Routing to relevant tables...'})}\n\n"
        
        # Execute Pipeline (RAG -> Rules -> LLM -> Validate -> DB)
        result = await execute_pipeline_with_retry(user_query)
        
        # Event 2: Data Chunk Streaming
        metadata_payload = {
            "sql": result["sql"],
            "latency_ms": result["latency_ms"],
            "confidence": result["confidence"],
            "retries": result["retries"]
        }
        
        async for chunk in result["results_stream"]:
            data_payload = {
                "results": chunk,
                **metadata_payload
            }
            yield f"event: data_chunk\ndata: {json.dumps(data_payload)}\n\n"
        
        # Event 3: Status (Synthesizing)
        yield f"event: status\ndata: {json.dumps({'step': 'llm', 'msg': 'Synthesizing final answer...'})}\n\n"
        
        # Synthesize Answer (using the faster 8b model)
        answer = await synthesize_results(user_query, result["sql"], result["first_chunk"])
        
        # Event 4: Complete
        yield f"event: complete\ndata: {json.dumps({'answer': answer})}\n\n"
        
    except ValueError as e: # Confidence rejection
        yield f"event: error\ndata: {json.dumps({'msg': str(e)})}\n\n"
    except SecurityViolationError as e:
        yield f"event: error\ndata: {json.dumps({'msg': f'Security Blocked: {str(e)}'})}\n\n"
    except QueryExecutionError as e:
        yield f"event: error\ndata: {json.dumps({'msg': f'Execution Error: {str(e)}'})}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'msg': f'Unexpected Error: {str(e)}'})}\n\n"

@app.post("/api/v1/stream", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def stream_query(req: QueryRequest, request: Request):
    """
    The main streaming endpoint for the frontend.
    """
    return StreamingResponse(
        stream_generator(req.query),
        media_type="text/event-stream"
    )

@app.get("/api/v1/health", dependencies=[Depends(verify_api_key)])
async def health_check():
    """
    Day 15: Basic health endpoint to verify the API, Database, and Vector Store are reachable.
    """
    db_status = "unreachable"
    try:
        conn = await get_connection()
        try:
            await conn.execute("SELECT 1")
            db_status = "healthy"
        finally:
            await conn.close()
    except Exception as e:
        db_status = f"error: {str(e)}"
        
    return {
        "status": "online",
        "database": db_status,
        "chromadb_version": chromadb.__version__
    }

@app.get("/api/v1/history", dependencies=[Depends(verify_api_key)])
async def query_history(limit: int = 20):
    """
    Day 16: Returns recent telemetry logs as JSON.
    Powers the frontend's telemetry panel.
    """
    logs = await get_recent_logs(limit=limit)
    return {"logs": logs}

if __name__ == "__main__":
    import uvicorn
    # Allow running directly via python -m src.api.server for testing
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)