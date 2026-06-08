"""Tool for retrieving context from Chroma."""

from langchain_chroma import Chroma
from langchain_core.tools import tool

from src.models import get_ali_embeddings

from .utils import (
    DEFAULT_CHROMA_PERSIST_DIRECTORY,
    DEFAULT_CHROMA_STORAGE_MODE,
    get_chroma_client,
    normalize_chroma_storage_mode,
    resolve_path,
)


@tool("retrieve_context")
def retrieve_context(
    query: str,
    storage_mode: str = DEFAULT_CHROMA_STORAGE_MODE,
    persist_directory: str = DEFAULT_CHROMA_PERSIST_DIRECTORY,
    collection_name: str = "codebase",
    k: int = 5,
) -> str:
    """Retrieve semantically relevant code context from Chroma local or memory storage."""
    try:
        normalized_storage_mode = normalize_chroma_storage_mode(storage_mode)
    except ValueError as error:
        return str(error)

    if normalized_storage_mode == "local":
        persist_path = resolve_path(persist_directory)
        if not persist_path.exists():
            return f"Chroma persist directory not found: {persist_path}. Run index_repository first."

    client = get_chroma_client(normalized_storage_mode, persist_directory)
    vector_store = Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=get_ali_embeddings(),
    )

    results = vector_store.similarity_search_with_score(query, k=k)
    if not results:
        return f"No context found for query: {query}"

    blocks: list[str] = []
    for rank, (document, score) in enumerate(results, start=1):
        metadata = document.metadata
        source = metadata.get("source", "unknown")
        start_line = metadata.get("start_line", "?")
        end_line = metadata.get("end_line", "?")
        blocks.append(
            "\n".join(
                [
                    f"[{rank}] {source}:{start_line}-{end_line} score={score}",
                    document.page_content.strip(),
                ]
            )
        )

    return "\n\n---\n\n".join(blocks)
