"""
Shared utilities for the QueryForce application.
"""
import os
import logging
import warnings


def suppress_chromadb_telemetry():
    """
    Silences all ChromaDB/Posthog telemetry warnings and stdout noise.
    Call this once at application startup before importing chromadb.
    """
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
