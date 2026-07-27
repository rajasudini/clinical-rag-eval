"""Metadata integrity checks (issue #1): every stored chunk is traceable to a
source, and that source metadata survives into retrieval. Offline — no OpenAI.
Run:  pytest 02-eval-suite/test_metadata.py -v
"""

import sys
from pathlib import Path

import chromadb

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "01-rag-chatbot" / "src"))
from config import CHROMA_DIR, COLLECTION, configure_settings
from rag_pipeline import load_index


def _stored_metadatas():
    db = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col = db.get_or_create_collection(COLLECTION)
    return col.get(include=["metadatas"])["metadatas"]


def test_every_chunk_has_a_source():
    metas = _stored_metadatas()
    assert metas, "index is empty — run ingest.py first"
    missing = [m for m in metas if not (m or {}).get("file_name")]
    assert not missing, f"{len(missing)} chunks are missing file_name"


def test_every_chunk_has_a_page_field():
    metas = _stored_metadatas()
    missing = [m for m in metas if not (m or {}).get("page_label")]
    assert not missing, f"{len(missing)} chunks have no page_label (PDFs need a page, .txt should be 'n/a')"


def test_retrieved_nodes_keep_source_metadata():
    configure_settings()
    index = load_index()
    nodes = index.as_retriever(similarity_top_k=4).retrieve(
        "What A1C level is recommended as a target?"
    )
    assert nodes, "retrieval returned nothing"
    for nws in nodes:
        assert nws.node.metadata.get("file_name"), "a retrieved chunk lost its source file_name"