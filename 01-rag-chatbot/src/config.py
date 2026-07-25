"""
Shared configuration for the clinical RAG system: paths, model choices,
chunking/retrieval params, the safety system prompt, and the global LlamaIndex
Settings wiring. Imported by BOTH ingest.py (build) and rag_pipeline.py (query),
so neither depends on the other.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai import OpenAI

# --- Paths (anchored to this file so scripts run from anywhere) ---
HERE = Path(__file__).resolve()
PROJECT = HERE.parents[1]                     # -> 01-rag-chatbot/
DOCS_DIR = PROJECT / "data" / "documents"
CHROMA_DIR = PROJECT / "chroma_db"
COLLECTION = "clinical_docs"

# --- Chunking ---
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50

# --- Models ---
EMBED_MODEL = "BAAI/bge-base-en-v1.5"   # local, private, free
LLM_MODEL = "gpt-4o-mini"                                 # OpenAI, for generation

# --- Retrieval ---
TOP_K = 4

# --- Clinical safety guardrail ---
SYSTEM_PROMPT = (
    "You are a diabetes information assistant. Answer using ONLY the provided "
    "context from official U.S. government clinical sources. If the context does "
    "not contain the answer, say you don't have that information rather than "
    "guessing. Do not diagnose, prescribe, or give individualized medical "
    "advice; recommend consulting a healthcare professional for personal "
    "decisions. Ground each factual claim in the retrieved sources."
)


def configure_settings():
    """Set the global LlamaIndex config: local embeddings + OpenAI LLM.
    temperature=0 keeps answers deterministic for reproducible evaluation."""
    load_dotenv(PROJECT.parent / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("ERROR: OPENAI_API_KEY not set. Copy .env.example to .env and fill it in.")

    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
    Settings.llm = OpenAI(model=LLM_MODEL, temperature=0, system_prompt=SYSTEM_PROMPT)