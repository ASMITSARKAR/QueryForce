import os
os.environ["CHROMA_TELEMETRY"] = "False" # Suppress the known ChromaDB bug
import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings
from pathlib import Path
from src.config import settings

def get_or_create_collection(collection_name: str = "schema_catalog") -> chromadb.Collection:
    """
    Initializes ChromaDB PersistentClient and returns the target collection.
    Applies the G3 Fix to ensure cosine space is used for 0-1 bounded confidence scores.
    """
    chroma_dir = Path(settings.CHROMA_DIR).absolute().as_posix()
    
    # Initialize persistent client
    client = chromadb.PersistentClient(path=chroma_dir, settings=Settings(anonymized_telemetry=False))
    
    # We use a lightweight local model for embedding schema DDL
    # This downloads the ~90MB weights on first run, which we will later bundle in Docker (Day 20)
    embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    
    # G3 Fix: Explicitly define the distance metric as 'cosine'
    # By default, Chroma uses Squared L2 (unbounded). Cosine distance is bounded.
    # Chroma returns distance = 1 - cosine_similarity. So (1 - distance) = confidence percentage.
    try:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=embedding_func
        )
    except ValueError:
        # Collection does not exist, create it with explicit metadata
        collection = client.create_collection(
            name=collection_name,
            embedding_function=embedding_func,
            metadata={
                "hnsw:space": "cosine",
                "collection_version": "v1.0" # Track schema generation versions
            }
        )
        
    return collection

if __name__ == "__main__":
    print("Initializing Vector Store...")
    col = get_or_create_collection()
    print(f"Collection '{col.name}' loaded successfully with {col.count()} documents.")
