"""
Phase 1 RAG pipeline for the diabetes-guidance assistant.

Built one stage at a time: load -> chunk -> embed -> store -> retrieve -> generate
This version covers STAGE 1 only: LOAD.
"""

from pathlib import Path

from llama_index.core import SimpleDirectoryReader

# Resolve paths from THIS file's location, so the script runs from any directory.
HERE = Path(__file__).resolve()
PROJECT = HERE.parents[1]                    # -> 01-rag-chatbot/
DOCS_DIR = PROJECT / "data" / "documents"


def load_documents():
    """Stage 1 (load): read every .pdf and .txt in the corpus directory."""
    reader = SimpleDirectoryReader(
        input_dir=str(DOCS_DIR),
        required_exts=[".pdf", ".txt"],
        recursive=False,
    )
    return reader.load_data()


def main():
    docs = load_documents()
    print(f"Loaded {len(docs)} Document objects from {DOCS_DIR.name}/\n")

    # Count how many Documents came from each source file.
    per_file = {}
    for d in docs:
        name = d.metadata.get("file_name", "?")
        per_file[name] = per_file.get(name, 0) + 1

    print("Documents per source file:")
    for name, count in sorted(per_file.items()):
        print(f"  {count:>4}  {name}")

    # Peek at the first Document to see real extracted text.
    first = docs[0]
    print("\n--- First Document ---")
    print("metadata:", first.metadata)
    preview = " ".join(first.get_content().split())[:300]
    print("text preview:", preview, "...")


if __name__ == "__main__":
    main()
