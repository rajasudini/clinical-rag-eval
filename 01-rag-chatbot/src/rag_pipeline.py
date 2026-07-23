"""
Phase 1 RAG pipeline for the diabetes-guidance assistant.

Built one stage at a time: load -> chunk -> embed -> store -> retrieve -> generate
This version covers STAGE 1 only: LOAD.
"""

from pathlib import Path

from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter

# Resolve paths from THIS file's location, so the script runs from any directory.
HERE = Path(__file__).resolve()
PROJECT = HERE.parents[1]                    # -> 01-rag-chatbot/
DOCS_DIR = PROJECT / "data" / "documents"

# --- Chunking config (a principled starting point; we tune this during eval) ---
CHUNK_SIZE = 512        # target tokens per chunk
CHUNK_OVERLAP = 50      # tokens shared between neighboring chunks

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
    docs = load_documents()
    print(f"Loaded {len(docs)} Document objects from {DOCS_DIR.name}/")

    nodes = chunk_documents(docs)
    print(f"Split into {len(nodes)} chunks (Nodes)\n")

    # Chunk-size stats (in characters; chunk_size is tokens, ~4 chars each).
    sizes = [len(n.get_content()) for n in nodes]
    print(f"Chunk length (chars): min={min(sizes)}  max={max(sizes)}  "
          f"avg={sum(sizes) // len(sizes)}")

    # Peek at the first two chunks to see real passages + their source metadata.
    for i in (0, 1):
        n = nodes[i]
        src = n.metadata.get("file_name", "?")
        page = n.metadata.get("page_label", "?")
        preview = " ".join(n.get_content().split())[:200]
        print(f"\n--- Chunk {i}  (from {src}, page {page}) ---")
        print(preview, "...")


if __name__ == "__main__":
    main()
