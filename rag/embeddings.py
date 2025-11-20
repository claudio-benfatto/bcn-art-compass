"""
Embedding generation using Google Gemini text-embedding-005.
"""

import os
from typing import Optional

import google.generativeai as genai

from observability import log_debug, log_error, log_info


class EmbeddingGenerator:
    """
    Wrapper for Google Gemini embedding generation.

    Uses text-embedding-005 model for generating embeddings
    from text descriptions of events and venues.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "models/text-embedding-004"):
        """
        Initialize the embedding generator.

        Args:
            api_key: Google AI API key. If None, reads from GOOGLE_API_KEY env var
            model_name: Name of the embedding model to use
        """
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Google API key is required. Set GOOGLE_API_KEY environment variable or pass api_key parameter."
            )

        genai.configure(api_key=self.api_key)
        log_info("embedding_generator_initialized", model=self.model_name)

    def generate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            task_type: Type of embedding task (RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY)

        Returns:
            List of float values representing the embedding vector
        """
        try:
            log_debug("generating_embedding", text_length=len(text), task_type=task_type)

            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type=task_type,
            )

            embedding = result["embedding"]
            log_debug("embedding_generated", embedding_dim=len(embedding))

            return embedding

        except Exception as e:
            log_error("embedding_generation_failed", error=str(e), text_length=len(text))
            raise

    def generate_embeddings_batch(
        self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            task_type: Type of embedding task

        Returns:
            List of embedding vectors
        """
        log_info("generating_embeddings_batch", num_texts=len(texts), task_type=task_type)

        embeddings = []
        for i, text in enumerate(texts):
            try:
                embedding = self.generate_embedding(text, task_type=task_type)
                embeddings.append(embedding)

                if (i + 1) % 10 == 0:
                    log_debug("batch_progress", processed=i + 1, total=len(texts))

            except Exception as e:
                log_error("batch_embedding_failed", index=i, error=str(e))
                # Continue with other texts rather than failing completely
                embeddings.append([0.0] * 768)  # Placeholder embedding

        log_info("embeddings_batch_complete", total=len(texts), successful=len(embeddings))
        return embeddings

    def generate_query_embedding(self, query: str) -> list[float]:
        """
        Generate embedding for a search query.

        Args:
            query: Search query text

        Returns:
            Embedding vector for the query
        """
        return self.generate_embedding(query, task_type="RETRIEVAL_QUERY")
