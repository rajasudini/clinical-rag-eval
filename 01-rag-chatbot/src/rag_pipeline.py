"""
Phase 1 RAG pipeline for the diabetes-guidance assistant.

Built one stage at a time: load -> chunk -> embed -> store -> retrieve -> generate
This version covers STAGES 1-3: LOAD + CHUNK + EMBED (model setup).
"""

from pathlib import Path

from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# Resolve paths from THIS file's location, so the script runs from any directory.
HERE = Path(__file__).resolve()
PROJECT = HERE.parents[1]                    # -> 01-rag-chatbot/
DOCS_DIR = PROJECT / "data" / "documents"

# --- Chunking config (a principled starting point; we tune this during eval) ---
CHUNK_SIZE = 512        # target tokens per chunk
CHUNK_OVERLAP = 50      # tokens shared between neighboring chunks

# --- Embedding model: local Hugging Face baseline (free, private, offline) ---
# 384-dim. Deliberate baseline; we'll compare stronger models during eval.
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

def configure_settings():
    """Set the global LlamaIndex config. For now, just the embedding model.

    Setting Settings.embed_model once means every component (indexing,
    retrieval) uses the same local model — no per-call wiring, and no data
    leaves the machine (relevant for healthcare privacy).
    """
    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)

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

def main():
    configure_settings()
    docs = load_documents()
    print(f"Loaded {len(docs)} Document objects from {DOCS_DIR.name}/")

    nodes = chunk_documents(docs)
    print(f"Split into {len(nodes)} chunks (Nodes)\n")

    # Stage 3 demo: embed ONE chunk to see what a vector looks like.
    sample_text = nodes[0].get_content()
    vector = Settings.embed_model.get_text_embedding(sample_text)
    print(f"\nEmbedded 1 sample chunk with {EMBED_MODEL}")
    print(f"  vector dimensions: {len(vector)}")
    print(f"  first 8 numbers:   {[round(x, 4) for x in vector[:8]]}")


if __name__ == "__main__":
    main()
