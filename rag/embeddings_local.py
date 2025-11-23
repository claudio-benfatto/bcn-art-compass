"""
Local embedding generation using Sentence Transformers.

Free alternative to Google's embedding API for local development.
NOTE: This module requires sentence-transformers which is not installed
in cloud deployments to save space and cost. Cloud deployments should use
Google's Gemini embeddings API instead.
"""

from typing import Optional

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

from observability import log_debug, log_error, log_info


class LocalEmbeddingGenerator:
    """
    Wrapper for local embedding generation using Sentence Transformers.

    Uses the 'all-MiniLM-L6-v2' model (default) which is:
    - Free and runs locally
    - Fast (produces 384-dimensional embeddings)
    - Good quality for semantic search
    - Only ~80MB download
    
    NOTE: Requires sentence-transformers to be installed. Not available
    in cloud deployments - use Gemini embeddings API instead.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the local embedding generator.

        Args:
            model_name: Name of the sentence-transformers model to use.
                       Default: 'all-MiniLM-L6-v2' (fast, good quality)
                       Alternative: 'all-mpnet-base-v2' (slower, better quality)
            
        Raises:
            RuntimeError: If sentence-transformers is not installed
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "This is expected in cloud deployments. "
                "Use Gemini embeddings API instead by setting USE_LOCAL_LLM=false"
            )
        
        self.model_name = model_name
        log_info("loading_local_embedding_model", model=model_name)

        self.model = SentenceTransformer(model_name)

        log_info("local_embedding_model_loaded", model=model_name)

    def generate_embedding(self, text: str, task_type: Optional[str] = None) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            task_type: Not used for local models (for API compatibility)

        Returns:
            List of float values representing the embedding vector
        """
        try:
            log_debug("generating_local_embedding", text_length=len(text))

            # Generate embedding
            embedding = self.model.encode(text, convert_to_numpy=True)
            embedding_list = embedding.tolist()

            log_debug("local_embedding_generated", embedding_dim=len(embedding_list))

            return embedding_list

        except Exception as e:
            log_error("local_embedding_generation_failed", error=str(e), text_length=len(text))
            raise

    def generate_embeddings_batch(self, texts: list[str], task_type: Optional[str] = None) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            task_type: Not used for local models (for API compatibility)

        Returns:
            List of embedding vectors
        """
        log_info("generating_local_embeddings_batch", num_texts=len(texts))

        try:
            # Batch encoding is much faster than individual
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
            embeddings_list = [emb.tolist() for emb in embeddings]

            log_info("local_embeddings_batch_complete", total=len(texts), successful=len(embeddings_list))
            return embeddings_list

        except Exception as e:
            log_error("local_batch_embedding_failed", error=str(e))
            raise

    def generate_query_embedding(self, query: str) -> list[float]:
        """
        Generate embedding for a search query.

        Args:
            query: Search query text

        Returns:
            Embedding vector for the query
        """
        return self.generate_embedding(query)
