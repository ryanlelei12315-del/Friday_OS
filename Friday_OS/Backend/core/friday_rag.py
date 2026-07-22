import os
from pathlib import Path

import chardet
import chromadb
from pypdf import PdfReader

FRIDAY_OS_DIR = os.path.expanduser("~/FridayOS_Workspace")
CHROMA_DIR = os.path.join(FRIDAY_OS_DIR, "chroma_db")

# Initialize ChromaDB persistent storage client
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
# Collection to index local knowledge assets
rag_collection = chroma_client.get_or_create_collection(name="friday_desktop_knowledge")

# File extensions that contain source code (line-based chunking preferred)
CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".c",
    ".cc",
    ".m",
    ".mm",
    ".sql",
    ".sh",
    ".bash",
    ".zsh",
    ".yaml",
    ".yml",
    ".json",
    ".xml",
    ".toml",
    ".ini",
    ".cfg",
}

# Narrative/document file extensions (sentence-boundary chunking preferred)
NARRATIVE_EXTENSIONS = {".md", ".txt", ".rst", ".pdf", ".doc", ".docx", ".rtf"}


def extract_text_from_file(file_path: Path) -> str:
    """Safely extracts text string contents from PDFs, text files, or raw code."""
    if file_path.suffix.lower() == ".pdf":
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except Exception as e:
            return f"Error parsing PDF layout strings: {str(e)}"

    # Handle text or source code files safely by identifying character encoding sets
    else:
        try:
            with open(file_path, "rb") as raw_file:
                raw_data = raw_file.read(4096)
                if not raw_data:
                    return ""
                encoding = chardet.detect(raw_data)["encoding"] or "utf-8"

            with open(file_path, "r", encoding=encoding, errors="ignore") as f:
                return f.read()
        except Exception as e:
            return f"Error reading text document: {str(e)}"


def _detect_file_type(file_path: Path) -> str:
    """Detect whether a file is code, narrative, or dense technical content."""
    ext = file_path.suffix.lower()
    if ext in CODE_EXTENSIONS:
        return "code"
    elif ext in NARRATIVE_EXTENSIONS:
        return "narrative"
    else:
        return "dense"


def _chunk_code(text: str, chunk_lines: int = 50, overlap_lines: int = 10) -> list:
    """Line-based chunking for source code to preserve syntax integrity."""
    lines = text.splitlines()
    chunks = []
    step = chunk_lines - overlap_lines
    for i in range(0, max(len(lines), 1), step):
        chunk = "\n".join(lines[i : i + chunk_lines])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def _chunk_narrative(
    text: str, chunk_size: int = 800, overlap_sentences: int = 2
) -> list:
    """Sentence-boundary chunking for narrative text (markdown, prose)."""
    import re

    # Split on sentence boundaries (period, newline, or double newline)
    sentences = re.split(r"(?<=[.!?])\s+|\n\n+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current_chunk = []
    current_word_count = 0

    for sentence in sentences:
        sentence_word_count = len(sentence.split())
        if current_word_count + sentence_word_count > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Keep last N sentences for overlap
            overlap_count = 0
            overlap_sentences_list = []
            for s in reversed(current_chunk):
                overlap_count += len(s.split())
                overlap_sentences_list.insert(0, s)
                if overlap_count >= 100:  # ~100 word overlap
                    break
            current_chunk = overlap_sentences_list
            current_word_count = sum(len(s.split()) for s in current_chunk)

        current_chunk.append(sentence)
        current_word_count += sentence_word_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def _chunk_dense(text: str, chunk_size: int = 400, overlap: int = 50) -> list:
    """Smaller chunks for dense technical documentation."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def chunk_text(
    text: str, file_path: Path = None, chunk_size: int = 600, overlap: int = 100
) -> list:
    """
    Splits long text blocks into smaller overlapping chunks for semantic retrieval clarity.

    Uses language-aware chunking:
    - Code files: line-based chunking (50 lines, 10 line overlap)
    - Narrative text: sentence-boundary chunking (800 words, ~100 word overlap)
    - Dense technical docs: smaller word-based chunks (400 words, 50 word overlap)
    """
    if file_path:
        file_type = _detect_file_type(file_path)
        if file_type == "code":
            return _chunk_code(text)
        elif file_type == "narrative":
            return _chunk_narrative(text)
        else:
            return _chunk_dense(text)

    # Fallback to original behavior if no file_path provided
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def ingest_local_document(path_to_file: str) -> str:
    """Chunks a file and uploads its data properties to the ChromaDB layout engine."""
    file_path = Path(path_to_file)
    if not file_path.exists():
        return f"File target path missing: {path_to_file}"

    text_content = extract_text_from_file(file_path)
    if not text_content.strip():
        return "Document parsed completely empty. Insertion canceled."

    chunks = chunk_text(text_content, file_path=file_path)

    documents_list = []
    ids_list = []
    metadatas_list = []

    for idx, chunk in enumerate(chunks):
        documents_list.append(chunk)
        ids_list.append(f"doc_{file_path.stem}_{idx}")
        metadatas_list.append(
            {
                "source_file": file_path.name,
                "absolute_path": str(file_path.absolute()),
                "chunk_index": idx,
            }
        )

    # Bulk insert text vector components into the vector persistence layer
    rag_collection.add(documents=documents_list, ids=ids_list, metadatas=metadatas_list)

    return f"Successfully split and indexed {len(chunks)} text blocks from '{file_path.name}' into RAG Memory Core."


def query_desktop_knowledge(search_query: str, max_results: int = 3) -> str:
    """Queries ChromaDB cache vector space for relevant knowledge tokens matching semantic definitions."""
    results = rag_collection.query(query_texts=[search_query], n_results=max_results)

    if not results or not results["documents"] or not results["documents"][0]:
        return "No corresponding context matching query target discovered within RAG database storage storage layers."

    context_blocks = []
    for idx, doc_text in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][idx]
        context_blocks.append(
            f"--- Context Segment from file [{meta['source_file']}]:\n{doc_text}\n"
        )

    return "\n".join(context_blocks)
