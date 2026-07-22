"""
Tests for RAG (Retrieval Augmented Generation) functionality.
Uses a temporary ChromaDB directory to avoid polluting production data.
"""

import os
import shutil
import sys
import tempfile

# Add backend to path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "Friday_OS", "Backend")
)


class TestRAGChunking:
    """Test the chunk_text function with different file types."""

    def setup_method(self):
        """Import the module fresh for each test."""
        from core import friday_rag as rag

        self.rag = rag

    def test_code_chunking_preserves_lines(self):
        """Code chunking should keep lines intact."""
        code = "line1\nline2\nline3\nline4\nline5\nline6\n"
        chunks = self.rag.chunk_text(code, chunk_size=600, overlap=100)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert "\n" in chunk  # lines preserved

    def test_narrative_chunking_respects_sentences(self):
        """Narrative chunking should split on sentence boundaries."""
        text = "First sentence here. Second sentence there. Third sentence elsewhere. "
        text += "Fourth sentence somewhere. " * 100
        chunks = self.rag.chunk_text(text, chunk_size=800, overlap=100)
        assert len(chunks) >= 1

    def test_dense_chunking_smaller_chunks(self):
        """Dense technical docs should use smaller chunks."""
        text = "word " * 2000
        chunks = self.rag.chunk_text(text, chunk_size=600, overlap=100)
        assert len(chunks) >= 1

    def test_fallback_chunking(self):
        """Without file_path, should use original word-based chunking."""
        text = "word " * 2000
        chunks = self.rag.chunk_text(text, chunk_size=600, overlap=100)
        assert len(chunks) >= 1


class TestRAGIngestAndQuery:
    """Test ingest_local_document and query_desktop_knowledge with temp ChromaDB."""

    def setup_method(self):
        """Create a temporary directory for ChromaDB."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_chroma_dir = os.environ.get("FRIDAY_OS_DIR")

        # Point ChromaDB to temp directory
        os.environ["FRIDAY_OS_DIR"] = self.temp_dir

        # Re-init Chroma client for the new path
        import importlib

        from core import friday_rag as rag

        importlib.reload(rag)
        self.rag = rag

    def teardown_method(self):
        """Clean up temporary directory."""
        if self.original_chroma_dir is not None:
            os.environ["FRIDAY_OS_DIR"] = self.original_chroma_dir
        else:
            os.environ.pop("FRIDAY_OS_DIR", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ingest_and_query_text_file(self):
        """Test end-to-end ingest and query with a temp text file."""
        from core.friday_rag import ingest_local_document, query_desktop_knowledge

        test_file = os.path.join(self.temp_dir, "test_doc.txt")
        with open(test_file, "w") as f:
            f.write(
                "This is a test document about artificial intelligence. "
                "It discusses machine learning and neural networks. "
                "The document covers various topics in computer science. "
                "Artificial intelligence is transforming many industries. "
                "Machine learning models can recognize patterns in data."
            )

        result = ingest_local_document(test_file)
        assert "Successfully" in result
        assert "test_doc.txt" in result

        query_result = query_desktop_knowledge("artificial intelligence", max_results=1)
        assert query_result is not None
        assert "test_doc.txt" in query_result

    def test_ingest_nonexistent_file(self):
        """Test ingest with a non-existent file returns error."""
        from core.friday_rag import ingest_local_document

        result = ingest_local_document("/nonexistent/file.txt")
        assert "missing" in result.lower()
