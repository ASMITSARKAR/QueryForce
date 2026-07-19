# QueryForce AI Analytics Engine

QueryForce is an intelligent, containerized database analytics engine that bridges the gap between natural language questions and raw SQL data execution. 

With built-in Retrieval-Augmented Generation (RAG) for database schema context, an AST Validator to prevent destructive queries, and a robust telemetry logging system, it provides a safe, seamless, and intelligent interface for exploring your database.

## Architecture Data-Flow

```mermaid
flowchart TD
    %% Define styles
    classDef client fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc
    classDef api fill:#0f172a,stroke:#8b5cf6,stroke-width:2px,color:#f8fafc
    classDef engine fill:#0f172a,stroke:#10b981,stroke-width:2px,color:#f8fafc
    classDef data fill:#0f172a,stroke:#f59e0b,stroke-width:2px,color:#f8fafc
    classDef ext fill:#1e293b,stroke:#ef4444,stroke-width:2px,color:#f8fafc,stroke-dasharray: 5 5

    %% Nodes
    UI[Web UI Dashboard\nSSE Consumer]:::client
    CLI[CLI Tester\nSSE Consumer]:::client

    API[FastAPI Router\n/api/v1/stream]:::api
    Auth{Auth Guard\nX-API-Key}:::api

    Orch[Orchestrator\nRetry Loop]:::engine
    RAG[RAG Router\nChromaDB Vector Search]:::engine
    LLM_SQL[Llama-3.3-70b\nSQL Generator]:::ext
    LLM_Synth[Llama-3.1-8b\nAnswer Synthesizer]:::ext
    AST[AST Validator\nsqlglot Security]:::engine
    Exec[SQLite Executor\nRead-Only Mode]:::engine

    AnalyticsDB[(Analytics DB\nSource Data)]:::data
    TelemetryDB[(Telemetry DB\nWAL Mode)]:::data

    %% Edges
    UI -->|1. Natural Language Query| API
    CLI -->|1. Natural Language Query| API
    
    API --> Auth
    Auth -->|Valid Key| Orch
    Auth -.->|Invalid Key| 401[401 Unauthorized]
    
    Orch -->|2. Route Intent| RAG
    RAG -->|3. Fetch Schema Context| Orch
    
    Orch -->|4. Prompt + Schema| LLM_SQL
    LLM_SQL -->|5. Raw SQL| Orch
    
    Orch -->|6. Validate AST| AST
    AST -.->|DML Detected! Block| Orch
    AST -->|SELECT OK| Exec
    
    Exec -->|7. Query| AnalyticsDB
    AnalyticsDB -->|8. Raw Results| Exec
    Exec --> Orch
    
    Orch -->|9. Results + Query| LLM_Synth
    LLM_Synth -->|10. Narrative Answer| Orch
    
    Orch -->|11. Async Log| TelemetryDB
    
    Orch -->|12. Stream Events| API
    API -->|SSE Stream\n(status, data, complete)| UI
```

## Setup & Deployment

### Run via Docker (Recommended)

1. **Clone the repository.**
2. **Add your environment variables** to a `.env` file:
   ```env
   QUERYFORCE_API_KEY=your_secure_password
   GROQ_API_KEY=your_groq_api_key
   ```
3. **Start the engine:**
   ```bash
   docker-compose up --build -d
   ```
4. **Access the Web Dashboard** at `http://localhost:8000`.

### Environment Variables

| Variable | Description |
|---|---|
| `QUERYFORCE_API_KEY` | Master password to protect the API endpoint. |
| `GROQ_API_KEY` | Required for LLM inference via Groq. |
| `TELEMETRY_DB_PATH` | Path to save telemetry logs (must use WAL mode). |
| `ANALYTICS_DB_PATH` | Path to the target read-only SQLite database. |
| `CHROMA_DIR` | Path to the persisted vector database directory. |
