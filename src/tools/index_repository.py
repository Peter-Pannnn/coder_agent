"""Tool for indexing a repository into Chroma."""

import hashlib

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool

from src.models import get_ali_embeddings

from .utils import (
    DEFAULT_CHROMA_PERSIST_DIRECTORY,
    DEFAULT_CHROMA_STORAGE_MODE,
    DEFAULT_INDEX_EXTENSIONS,
    chunk_text,
    get_chroma_client,
    iter_files,
    normalize_chroma_storage_mode,
    read_text_file,
    resolve_path,
)


@tool("index_repository")
def index_repository(
    target_path: str = ".",
    storage_mode: str = DEFAULT_CHROMA_STORAGE_MODE,
    persist_directory: str = DEFAULT_CHROMA_PERSIST_DIRECTORY,
    collection_name: str = "codebase",
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    max_file_size_kb: int = 512,
) -> str:
    """Index repository text/code files into Chroma using local or memory storage."""
    try:
        normalized_storage_mode = normalize_chroma_storage_mode(storage_mode)
    except ValueError as error:
        return str(error)

    target = resolve_path(target_path)
    if not target.exists():
        return f"Path not found: {target}"

    source_root = target if target.is_dir() else target.parent
    target_files = iter_files(target) if target.is_dir() else [target]
    target_type = "directory" if target.is_dir() else "file"

    documents: list[Document] = []
    ids: list[str] = []
    skipped = 0

    for file_path in target_files:
        if file_path.suffix.lower() not in DEFAULT_INDEX_EXTENSIONS:
            skipped += 1
            continue
        try:
            if file_path.stat().st_size > max_file_size_kb * 1024:
                skipped += 1
                continue
            text = read_text_file(file_path)
        except OSError:
            skipped += 1
            continue

        if not text.strip():
            skipped += 1
            continue

        relative_path = file_path.relative_to(source_root).as_posix()
        for chunk_index, (start_line, end_line, chunk) in enumerate(
            chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        ):
            if not chunk.strip():
                continue
            metadata = {
                "source": relative_path,
                "absolute_path": str(file_path),
                "start_line": start_line,
                "end_line": end_line,
                "file_extension": file_path.suffix.lower(),
            }
            documents.append(Document(page_content=chunk, metadata=metadata))
            digest = hashlib.sha1(f"{relative_path}:{chunk_index}:{chunk}".encode("utf-8")).hexdigest()
            ids.append(digest)

    if not documents:
        return f"No indexable files found under: {target}"

    client = get_chroma_client(normalized_storage_mode, persist_directory)
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    vector_store = Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=get_ali_embeddings(),
    )
    vector_store.add_documents(documents=documents, ids=ids)

    lines = [
        f"Indexed target: {target}",
        f"Target type: {target_type}",
        f"Storage mode: {normalized_storage_mode}",
        f"Collection: {collection_name}",
    ]
    if normalized_storage_mode == "local":
        lines.append(f"Persist directory: {resolve_path(persist_directory)}")
    else:
        lines.append("Persist directory: memory only")
    lines.extend(
        [
            f"Documents: {len(documents)}",
            f"Skipped files: {skipped}",
        ]
    )
    return "\n".join(lines)


