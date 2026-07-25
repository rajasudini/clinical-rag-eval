"""
Query pipeline for the diabetes RAG assistant: attach to the prebuilt Chroma
index and answer questions (retrieve -> generate), returning the answer plus the
source chunks used (needed for evaluation).

Build the index first with ingest.py, then:
    python 01-rag-chatbot/src/rag_pipeline.py   # answer one demo question
"""

import chromadb
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore

from config import CHROMA_DIR, COLLECTION, TOP_K, configure_settings


def load_index():
    """Attach to the already-built Chroma index. Raises if it hasn't been built
    yet — run ingest.py first. (Query path never builds.)"""
    db = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = db.get_or_create_collection(COLLECTION)
    if collection.count() == 0:
        raise SystemExit(
            "Index is empty. Build it first:\n"
            "    python 01-rag-chatbot/src/ingest.py"
        )
    vector_store = ChromaVectorStore(chroma_collection=collection)
    return VectorStoreIndex.from_vector_store(vector_store)


def ask(index, question, top_k=TOP_K):
    """Retrieve top_k chunks and answer with the LLM. Returns answer + the source
    chunks it used, so the evaluation harness can score both."""
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
    index = load_index()

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