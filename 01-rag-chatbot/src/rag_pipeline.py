"""
Phase 1 RAG pipeline for the diabetes-guidance assistant.

Built one stage at a time: load -> chunk -> embed -> store -> retrieve -> generate
This version is the COMPLETE pipeline (Stages 1-6).
"""

import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.chroma import ChromaVectorStore

# Resolve paths from THIS file's location, so the script runs from any directory.
HERE = Path(__file__).resolve()
PROJECT = HERE.parents[1]                    # -> 01-rag-chatbot/
DOCS_DIR = PROJECT / "data" / "documents"
CHROMA_DIR = PROJECT / "chroma_db"           # persisted vector store (gitignored)
COLLECTION = "clinical_docs"                 # name of our table inside Chroma

# --- Chunking config (a principled starting point; we tune this during eval) ---
CHUNK_SIZE = 512        # target tokens per chunk
CHUNK_OVERLAP = 50      # tokens shared between neighboring chunks

# --- Embedding model: local Hugging Face baseline (free, private, offline) ---
# 384-dim. Deliberate baseline; we'll compare stronger models during eval.
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"   # local, private, free
LLM_MODEL = "gpt-4o-mini"                                 # OpenAI, for generation

# --- Retrieval config ---
TOP_K = 4        # how many chunks to pull back per question (tune later)

# --- Clinical safety guardrail: grounding + boundaries ---
SYSTEM_PROMPT = (
    "You are a diabetes information assistant. Answer using ONLY the provided "
    "context from official U.S. government clinical sources. If the context does "
    "not contain the answer, say you don't have that information rather than "
    "guessing. Do not diagnose, prescribe, or give individualized medical "
    "advice; recommend consulting a healthcare professional for personal "
    "decisions. Ground each factual claim in the retrieved sources."
)

def configure_settings():
    """Set global LlamaIndex config: embedding model (local) + LLM (OpenAI).

    temperature=0 makes answers as deterministic as the API allows, which
    matters when the eval harness replays the same questions.
    """
    load_dotenv(PROJECT.parent / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("ERROR: OPENAI_API_KEY not set. Copy .env.example to .env and fill it in.")

    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
    Settings.llm = OpenAI(model=LLM_MODEL, temperature=0, system_prompt=SYSTEM_PROMPT)

def load_documents():
    """Stage 1 (load): read every .pdf and .txt in the corpus directory."""
    reader = SimpleDirectoryReader(
        input_dir=str(DOCS_DIR),
        required_exts=[".pdf", ".txt"],
        recursive=False,
    )
    return reader.load_data()

def chunk_documents(docs):
    """Stage 2 (chunk): split page-Documents into overlapping passage Nodes.

    SentenceSplitter breaks on sentence boundaries where possible, so facts
    (e.g. "metformin 500 mg") aren't cut in half. Each Node inherits its
    parent Document's metadata (file_name, page_label) for later citations.
    """
    splitter = SentenceSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.get_nodes_from_documents(docs)

def get_index(rebuild=False):
    """Stages 3-4 (embed + store): build the Chroma-backed index, or reuse it.

    First run: chunk -> embed all chunks -> write vectors to Chroma on disk.
    Later runs: attach to the already-stored vectors (no re-embedding).
    Pass rebuild=True to wipe and re-index from scratch.
    """
    if rebuild and CHROMA_DIR.exists():
        import shutil
        shutil.rmtree(CHROMA_DIR)
        print(f"[rebuild] cleared {CHROMA_DIR.name}/")

    # Open (or create) the persistent Chroma DB and our collection.
    db = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = db.get_or_create_collection(COLLECTION)
    vector_store = ChromaVectorStore(chroma_collection=collection)

    if collection.count() == 0:
        # --- First-time indexing: load -> chunk -> embed -> store ---
        print("[index] empty store; indexing corpus (one-time)...")
        docs = load_documents()
        nodes = chunk_documents(docs)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex(nodes, storage_context=storage_context,
                                 show_progress=True)
        print(f"[index] stored {collection.count()} vectors in {CHROMA_DIR.name}/")
    else:
        # --- Reuse: attach to already-embedded vectors ---
        print(f"[index] reusing {collection.count()} vectors from {CHROMA_DIR.name}/")
        index = VectorStoreIndex.from_vector_store(vector_store)

    return index

def ask(index, question, top_k=TOP_K):
    """Stage 6 (generate): retrieve top_k chunks and answer with the LLM.

    Returns answer AND the source chunks it used, so the evaluation harness can
    score both the answer and what was retrieved.
    """
    query_engine = index.as_query_engine(similarity_top_k=top_k)
    response = query_engine.query(question)

    sources = []
    for nws in response.source_nodes:
        sources.append({
            "file": nws.node.metadata.get("file_name", "?"),
            "page": nws.node.metadata.get("page_label", "?"),
            "score": round(nws.score, 4) if nws.score is not None else None,
            "text": nws.node.get_content(),
        })

    return {"question": question, "answer": str(response).strip(), "sources": sources}

def main():
    configure_settings()
    index = get_index()
    
    question = "What A1C level is recommended as a target for many adults with diabetes?"
    result = ask(index, question)

    print(f"\nQ: {result['question']}")
    print("-" * 70)
    print(result["answer"])
    print("-" * 70)
    print(f"Sources ({len(result['sources'])}):")
    for i, s in enumerate(result["sources"], 1):
        print(f"  [{i}] {s['file']} (page {s['page']})  score={s['score']}")


if __name__ == "__main__":
    main()
