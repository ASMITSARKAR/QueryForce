import asyncio
import httpx
import json
import sys
from src.config import settings

async def main():
    url = "http://127.0.0.1:8000/api/v1/stream"
    headers = {
        "X-API-Key": settings.QUERYFORCE_API_KEY.get_secret_value(),
        "Content-Type": "application/json"
    }
    
    # Allow passing a custom query as an argument, otherwise use default
    query = sys.argv[1] if len(sys.argv) > 1 else "Count all customers"
    payload = {"query": query}

    print(f"Connecting to {url}...")
    print(f"Query: '{query}'\n")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                
                print("--- STREAM STARTED ---\n")
                
                # Parse SSE events from the stream
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        print(f"[{line[7:].upper()}]", end=" ")
                    elif line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data_json = json.loads(data_str)
                            
                            # Pretty print based on event type
                            if "step" in data_json:
                                print(f"-> {data_json['msg']}")
                            elif "sql" in data_json:
                                print(f"-> SQL Generated: {data_json['sql']}")
                                print(f"       Rows Returned: {len(data_json['results'])}")
                            elif "answer" in data_json:
                                print(f"-> Final Answer: {data_json['answer']}")
                            elif "msg" in data_json:
                                print(f"-> Error/Message: {data_json['msg']}")
                            else:
                                print(f"-> {data_json}")
                        except json.JSONDecodeError:
                            print(f"-> {data_str}")
                    elif not line.strip():
                        # Empty line separates SSE events
                        pass
                
                print("\n--- STREAM COMPLETE ---")
                
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code}")
        print(e.response.text)
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
