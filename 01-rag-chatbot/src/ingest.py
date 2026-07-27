"""
Ingestion pipeline: build (or rebuild) the Chroma vector index from the corpus.
load -> chunk -> embed -> store. Run offline: once, or after the corpus / chunk
config / embedding model changes.

    python 01-rag-chatbot/src/ingest.py            # build if not already built
    python 01-rag-chatbot/src/ingest.py --rebuild  # wipe and re-index
"""

import argparse
import shutil

import chromadb
from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore

from config import (
    CHROMA_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION,
    DOCS_DIR,
    configure_settings,
)


def load_documents():
    """Read every .pdf and .txt in the corpus folder."""
    reader = SimpleDirectoryReader(
        input_dir=str(DOCS_DIR),
        required_exts=[".pdf", ".txt"],
        recursive=False,
    )
    return reader.load_data()


def chunk_documents(docs):
    """Split the loaded docs into smaller overlapping chunks (nodes). Give .txt
    chunks an explicit page_label so every chunk has a traceable source + page."""
    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(docs)
    for n in nodes:
        if n.metadata.get("file_name", "").endswith(".txt"):
            n.metadata.setdefault("page_label", "n/a")
    return nodes

def build_index(rebuild=False):
    """Load, chunk, embed, and store everything into Chroma. Skips the work if
    it's already built, unless rebuild=True wipes it and starts fresh."""
    if rebuild and CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
        print(f"[ingest] cleared {CHROMA_DIR.name}/")

    db = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = db.get_or_create_collection(COLLECTION)
    vector_store = ChromaVectorStore(chroma_collection=collection)

    if collection.count() > 0:
        print(f"[ingest] already built ({collection.count()} vectors). Use --rebuild to force.")
        return

    print("[ingest] indexing corpus...")
    docs = load_documents()
    nodes = chunk_documents(docs)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex(nodes, storage_context=storage_context, show_progress=True)
    print(f"[ingest] stored {collection.count()} vectors in {CHROMA_DIR.name}/")


def main():
    parser = argparse.ArgumentParser(description="Build/rebuild the RAG vector index.")
    parser.add_argument("--rebuild", action="store_true",
                        help="wipe and re-index from scratch")
    args = parser.parse_args()

    configure_settings()          # embed model must be set before embedding chunks
    build_index(rebuild=args.rebuild)
    print("Ingestion complete.")


if __name__ == "__main__":
    main()