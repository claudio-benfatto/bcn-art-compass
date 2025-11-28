"""
ChromaDB vector store wrapper for event and venue search.

Uses local ChromaDB with local sentence-transformer embeddings.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    Settings = None

from observability import log_info, log_rag_query
from rag.embeddings_local import LocalEmbeddingGenerator
from rag.models import EventWithVenue, SearchResult

if TYPE_CHECKING:
    from memory.models import UserProfile


class VectorStore:
    """
    ChromaDB-based vector store for events and venues.

    Handles document indexing and semantic search with local embeddings.
    Designed for local development with no cloud dependencies.
    """

    def __init__(
        self,
        collection_name: str = "events",
        persist_directory: Optional[str] = None,
        embedding_generator: Optional[LocalEmbeddingGenerator] = None,
    ):
        """
        Initialize the vector store.

        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist the database. If None, uses ./storage/chroma_db
            embedding_generator: LocalEmbeddingGenerator instance. If None, creates a new one
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb is not installed. Install with: uv sync --extra local"
            )
        
        self.collection_name = collection_name

        # Set up persistence directory
        if persist_directory is None:
            persist_directory = str(Path(__file__).parent.parent / "storage" / "chroma_db")

        os.makedirs(persist_directory, exist_ok=True)

        # Initialize ChromaDB persistent client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
            )
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Cultural events and venues in Barcelona"},
        )

        # Initialize local embedding generator
        self.embedding_generator = embedding_generator or LocalEmbeddingGenerator()

        log_info(
            "vector_store_initialized",
            collection=collection_name,
            persist_directory=persist_directory,
            doc_count=self.collection.count(),
            embedding_type="local",
        )

    def add_documents(self, events_with_venues: list[EventWithVenue]) -> None:
        """
        Add events and venues to the vector store.

        Args:
            events_with_venues: List of EventWithVenue objects to index
        """
        if not events_with_venues:
            log_info("no_documents_to_add")
            return

        log_info("adding_documents_to_vector_store", count=len(events_with_venues))

        # Prepare data for ChromaDB
        ids = []
        documents = []
        metadatas = []

        for ewv in events_with_venues:
            ids.append(ewv.event.id)
            documents.append(ewv.to_text())

            # Store metadata for filtering and result reconstruction
            metadatas.append(
                {
                    "event_id": ewv.event.id,
                    "title": ewv.event.title,
                    "venue_id": ewv.venue.id,
                    "venue_name": ewv.venue.name,
                    "genres": ",".join(ewv.event.genres),
                    "tags": ",".join(ewv.event.tags),
                    "neighborhood": ewv.venue.neighborhood,
                    "start_date": str(ewv.event.start_date),
                    "end_date": str(ewv.event.end_date),
                    "cost_range": ewv.event.cost_range,
                    "url": ewv.event.url,
                    # Added lat/lon for downstream distance calculation & reasoning.
                    "venue_latitude": getattr(ewv.venue, "latitude", None),
                    "venue_longitude": getattr(ewv.venue, "longitude", None),
                }
            )

        # Generate embeddings
        log_info("generating_embeddings_for_documents", count=len(documents))
        embeddings = self.embedding_generator.generate_embeddings_batch(documents)

        # Add to collection
        self.collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

        log_info("documents_added_successfully", count=len(ids), total_in_store=self.collection.count())

    def query(
        self,
        query_text: str,
        k: int = 5,
        filters: Optional[dict] = None,
        profile: Optional["UserProfile"] = None,
    ) -> list[SearchResult]:
        """
        Query the vector store for relevant events.

        In Milestone 2, adds profile-based scoring to personalize results.

        Args:
            query_text: Natural language search query
            k: Number of results to return
            filters: Optional metadata filters (e.g., {"genres": "sculpture"})
            profile: Optional user profile for personalized ranking

        Returns:
            List of SearchResult objects ordered by relevance
        """
        log_rag_query(query=query_text, num_results=k, filters=filters)

        # Generate query embedding
        query_embedding = self.embedding_generator.generate_query_embedding(query_text)

        # Build where clause for filters if provided
        where_clause = None
        if filters:
            # Convert filters to ChromaDB where clause format
            # For now, simple equality filters
            where_clause = filters

        # Query more results if we have a profile (to allow for re-ranking)
        fetch_k = k * 3 if profile else k

        # Query the collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_k,
            where=where_clause,
        )

        # Convert to SearchResult objects
        search_results = []

        if results["ids"] and results["ids"][0]:
            for i, event_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i] if results["distances"] else 0.0

                # Convert distance to similarity score (closer = higher score)
                base_score = 1.0 / (1.0 + distance)

                # Apply profile-based scoring if available
                final_score = self._apply_profile_scoring(base_score, metadata, profile)

                search_results.append(
                    SearchResult(
                        event_id=event_id,
                        title=metadata["title"],
                        description=results["documents"][0][i].split("\n")[1].replace("Description: ", ""),
                        venue_name=metadata["venue_name"],
                        genres=metadata["genres"].split(","),
                        start_date=metadata["start_date"],
                        end_date=metadata["end_date"],
                        cost_range=metadata["cost_range"],
                        score=final_score,
                        url=metadata["url"],
                        venue_latitude=metadata.get("venue_latitude"),
                        venue_longitude=metadata.get("venue_longitude"),
                    )
                )

        # Sort by score (highest first) if profile was used for re-ranking
        if profile:
            search_results.sort(key=lambda x: x.score, reverse=True)
            search_results = search_results[:k]  # Trim to requested k

        log_info("query_complete", results_found=len(search_results), query=query_text)
        return search_results

    def clear(self) -> None:
        """Clear all documents from the collection."""
        log_info("clearing_vector_store", collection=self.collection_name)
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Cultural events and venues in Barcelona"},
        )
        log_info("vector_store_cleared")

    def count(self) -> int:
        """Get the number of documents in the collection."""
        return self.collection.count()

    def _apply_profile_scoring(
        self,
        base_score: float,
        metadata: dict,
        profile: Optional["UserProfile"],
    ) -> float:
        """
        Apply profile-based scoring adjustments.

        Boosts score for events matching user's favorite genres/artists.
        Penalizes score for disliked genres.

        Args:
            base_score: Base similarity score from vector search
            metadata: Event metadata containing genres, artists, etc.
            profile: User profile (if None, returns base_score)

        Returns:
            Adjusted score
        """
        if not profile:
            return base_score

        score = base_score
        genres = metadata.get("genres", "").lower().split(",")

        # Boost for favorite genres (up to +0.2 per match)
        for fav_genre in profile.favorite_genres:
            if any(fav_genre.lower() in genre for genre in genres):
                score += 0.2
                log_info(
                    "profile_boost_applied",
                    event_title=metadata["title"],
                    genre=fav_genre,
                    boost=0.2,
                )

        # Penalize for disliked genres (up to -0.3 per match)
        for disliked_genre in profile.disliked_genres:
            if any(disliked_genre.lower() in genre for genre in genres):
                score -= 0.3
                log_info(
                    "profile_penalty_applied",
                    event_title=metadata["title"],
                    genre=disliked_genre,
                    penalty=-0.3,
                )

        # Boost for favorite artists (future enhancement when artist metadata is added)
        # for fav_artist in profile.favorite_artists:
        #     if any(fav_artist.lower() in artist for artist in artists):
        #         score += 0.15

        return max(0.0, score)  # Ensure score doesn't go negative
