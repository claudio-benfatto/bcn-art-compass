"""
Vertex AI Vector Search wrapper for cloud deployment.

This module provides a VectorStore implementation using Google Cloud's
Vertex AI Vector Search (Matching Engine).

Updated: 2025-01-19 - Fixed venue coordinate access (venue.latitude/venue.longitude)
"""

import os
from typing import Any

from google.cloud import aiplatform
from google.cloud.aiplatform_v1 import MatchServiceClient
from google.cloud.aiplatform_v1.types import FindNeighborsRequest

from observability import log_error, log_info, log_rag_query
from rag.data_loader import load_events
from rag.models import Event, EventWithVenue, SearchResult


class VertexVectorStore:
    """
    Vertex AI Vector Search implementation.

    Uses Google Cloud's Vertex AI Matching Engine for similarity search.
    """

    def __init__(
        self,
        project_id: str,
        location: str,
        index_endpoint: str,
        deployed_index_id: str,
        data_dir: str = "data",
    ):
        """
        Initialize Vertex AI Vector Search client.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region (e.g., 'europe-southwest1')
            index_endpoint: Full resource name of the index endpoint
            deployed_index_id: ID of the deployed index
            data_dir: Directory containing events.yaml
        """
        self.project_id = project_id
        self.location = location
        self.index_endpoint_name = index_endpoint
        self.deployed_index_id = deployed_index_id
        self.data_dir = data_dir

        # Initialize Vertex AI
        aiplatform.init(project=project_id, location=location)

        # Get the public endpoint domain if available
        # For public endpoints, we need the domain name in format: ENDPOINT_ID.LOCATION-PROJECT_NUMBER.vdb.vertexai.goog
        # Check if we can extract it from the resource name
        try:
            from google.cloud.aiplatform import matching_engine
            # Get endpoint details to find public domain
            endpoint_id = index_endpoint.split("/")[-1]
            endpoint_client = matching_engine.MatchingEngineIndexEndpoint(index_endpoint_name=index_endpoint)
            
            # The SDK should automatically handle public endpoints
            self.endpoint = endpoint_client
            log_info("vertex_endpoint_initialized", endpoint_id=endpoint_id)
        except Exception as e:
            log_error("vertex_endpoint_init_failed", error=str(e))
            raise

        # Load events from data file (for metadata lookup)
        self.events_map = {}
        try:
            from rag.data_loader import load_events_with_venues
            import os
            events_file = os.path.join(data_dir, "events.yaml")
            venues_file = os.path.join(data_dir, "venues.yaml")
            events_with_venues = load_events_with_venues(
                events_file=events_file, venues_file=venues_file
            )
            self.events_map = {e.event.id: e for e in events_with_venues}
            log_info(
                "vertex_events_loaded",
                count=len(self.events_map),
                events_file=events_file,
            )
        except Exception as e:
            log_error("vertex_events_load_failed", data_dir=data_dir, error=str(e))

    def query(
        self,
        query: str,
        k: int = 5,
        profile: Any = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Query the Vertex AI index for similar documents.

        Args:
            query: Query text (will be embedded)
            k: Number of results to return
            profile: User profile for scoring (not used yet)
            filters: Optional filters (not fully implemented)

        Returns:
            List of SearchResult objects
        """
        try:
            # Generate query embedding using Gemini
            log_rag_query(query=query, num_results=k, filters=filters, source="vertex_ai")
            from rag.embeddings import EmbeddingGenerator
            embedder = EmbeddingGenerator()
            query_embedding = embedder.generate_embedding(query, task_type="RETRIEVAL_QUERY")
            log_info(
                "vertex_embedding_generated",
                query=query,
                dimension=len(query_embedding),
            )

            # Query the endpoint
            log_info(
                "vertex_querying_endpoint",
                deployed_index_id=self.deployed_index_id,
                k=k,
            )
            
            # Try using find_neighbors instead of match for better public endpoint support
            response = self.endpoint.find_neighbors(
                deployed_index_id=self.deployed_index_id,
                queries=[query_embedding],
                num_neighbors=k,
            )
            log_info(
                "vertex_response_received",
                response_type=type(response).__name__,
                response_len=len(response) if response else 0,
            )

            # Parse results and populate with event data
            results = []
            if response and len(response) > 0:
                log_info("vertex_processing_matches", match_count=len(response[0]))
                for match in response[0]:
                    event_id = match.id
                    distance = getattr(match, 'distance', 0.0)
                    log_info("vertex_match_found", event_id=event_id, distance=distance)
                    
                    # Look up full event data
                    if event_id in self.events_map:
                        ewv = self.events_map[event_id]
                        # Convert EventWithVenue to SearchResult
                        search_result = SearchResult(
                            event_id=ewv.event.id,
                            title=ewv.event.title,
                            description=ewv.event.description,
                            venue_name=ewv.venue.name,
                            genres=ewv.event.genres,
                            start_date=ewv.event.start_date,
                            end_date=ewv.event.end_date,
                            cost_range=ewv.event.cost_range,
                            score=1.0 - distance,  # Convert distance to similarity
                            url=ewv.event.url,
                            venue_latitude=ewv.venue.latitude,
                            venue_longitude=ewv.venue.longitude,
                        )
                        results.append(search_result)
                        log_info("vertex_event_added", event_title=ewv.event.title)
                    else:
                        keys_sample = list(self.events_map.keys())[:5]
                        log_error(
                            "vertex_event_not_found",
                            event_id=event_id,
                            available_sample=keys_sample,
                        )
            else:
                log_info("vertex_no_matches")

            log_info("vertex_query_complete", results_count=len(results), query=query)
            return results

        except Exception as e:
            log_error("vertex_query_failed", query=query, error=str(e))
            return []

    def add_documents(self, events: list[Event]) -> None:
        """
        Add documents to the index.
        
        Note: In Vertex AI, documents are typically added via batch upload
        to GCS, not through this method. This is a placeholder.
        """
        raise NotImplementedError(
            "Adding documents to Vertex AI requires batch upload via GCS. "
            "Use the update_vertex_index.sh script instead."
        )

    def count(self) -> int:
        """
        Get the number of documents in the index.
        
        Note: This would require querying the index metadata.
        """
        # This would need to query the index details
        return -1  # Unknown

    @classmethod
    def from_env(cls) -> "VertexVectorStore":
        """
        Create VertexVectorStore from environment variables.

        Required environment variables:
        - GOOGLE_CLOUD_PROJECT or VERTEX_PROJECT_ID
        - GOOGLE_CLOUD_LOCATION or VERTEX_LOCATION
        - VERTEX_INDEX_ENDPOINT
        - VERTEX_DEPLOYED_INDEX_ID
        """
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT_ID")
        location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEX_LOCATION")
        index_endpoint = os.getenv("VERTEX_INDEX_ENDPOINT")
        deployed_index_id = os.getenv("VERTEX_DEPLOYED_INDEX_ID")

        if not all([project_id, location, index_endpoint, deployed_index_id]):
            raise ValueError(
                "Missing required environment variables for Vertex AI. "
                "Required: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, "
                "VERTEX_INDEX_ENDPOINT, VERTEX_DEPLOYED_INDEX_ID"
            )

        return cls(
            project_id=project_id,
            location=location,
            index_endpoint=index_endpoint,
            deployed_index_id=deployed_index_id,
        )
