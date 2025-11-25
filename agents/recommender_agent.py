"""
Recommender Agent - handles event recommendations with profile-based ranking.

This agent is responsible for:
- Querying the RAG vector store
- Applying profile-based scoring adjustments
- Ranking and filtering results
- Formatting recommendations for users

Part of Milestone 4: Clean Multi-Agent Workflow
A2A-compliant for future agent-to-agent communication.
"""

from typing import TYPE_CHECKING, List, Optional, Union

import google.generativeai as genai

from agents.a2a_protocol import A2AAgent, A2AMessage, AgentCapability, MessageType
from observability import log_error, log_info
from rag.models import EventWithVenue, SearchResult
from rag.vector_store import VectorStore
from tools.geocoder import geocoder_tool

if TYPE_CHECKING:
    from memory.models import UserProfile


class RecommenderAgent(A2AAgent):
    """
    Agent specialized in generating personalized event recommendations.

    Uses RAG for semantic search and applies user profile preferences
    to refine and rank results. Includes distance-based scoring when user
    location is available.
    """

    def __init__(self, vector_store: Optional[VectorStore] = None, api_key: Optional[str] = None):
        """
        Initialize the recommender agent.

        Args:
            vector_store: VectorStore instance for RAG queries. If None, creates a new one
            api_key: Google API key for Gemini (uses env GOOGLE_API_KEY if not provided)
        """
        # Initialize A2A protocol base
        super().__init__(agent_id="recommender_agent", name="RecommenderAgent")

        # Register capabilities
        self.register_capability(AgentCapability(
            name="recommend",
            description="Generate personalized event recommendations",
            input_schema={
                "query": "string",
                "profile": "UserProfile (optional)",
                "k": "integer (optional)",
            },
            output_schema={"recommendations": "list[EventWithVenue]"},
        ))

        # Store vector_store (may be None in cloud without proper setup)
        self.vector_store = vector_store
        self.geocoder = geocoder_tool

        # Initialize LLM for ranking
        self.llm_client = None
        self.llm_backend = None

        if api_key:
            # Use Gemini
            genai.configure(api_key=api_key)
            self.llm_client = genai.GenerativeModel("gemini-2.5-flash")
            self.llm_backend = "gemini"
        else:
            # Try Ollama for local development
            import os
            self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
            self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            self.llm_backend = "ollama"

        log_info(
            "recommender_agent_initialized",
            has_vector_store=vector_store is not None,
            llm_backend=self.llm_backend
        )

    def recommend(
        self,
        query: str,
        profile: Optional["UserProfile"] = None,
        k: int = 5,
        filters: Optional[dict] = None,
    ) -> List[Union[EventWithVenue, SearchResult]]:
        """
        Generate personalized event recommendations.

        Args:
            query: User's search query
            profile: User profile with preferences (optional)
            k: Number of results to return
            filters: Additional filters (e.g., date range, location)

        Returns:
            List of EventWithVenue or SearchResult objects, ranked by relevance and preferences

        Example:
            >>> agent = RecommenderAgent()
            >>> results = agent.recommend("contemporary art", profile=user_profile, k=5)
        """
        log_info(
            "generating_recommendations",
            query=query[:100],
            has_profile=profile is not None,
            has_vector_store=self.vector_store is not None,
            k=k,
        )

        # Check if vector store is available
        if self.vector_store is None:
            log_error(
                "vector_store_not_available",
                message="Cannot generate recommendations without vector store",
            )
            return []

        # Query vector store with profile-aware scoring
        results = self.vector_store.query(
            query,
            k=k,
            profile=profile,
            filters=filters or {},
        )

        if profile:
            # Apply LLM-based ranking with all context
            results = self._apply_llm_ranking(results, profile)
        else:
            # No profile, sort by RAG score
            results.sort(key=lambda x: getattr(x, "score", 0.0), reverse=True)

        log_info(
            "recommendations_generated",
            num_results=len(results),
            has_preferences=profile is not None and len(profile.favorite_genres) > 0,
        )

        return results

    def _apply_llm_ranking(
        self,
        results: List[Union[EventWithVenue, SearchResult]],
        profile: "UserProfile",
    ) -> List[Union[EventWithVenue, SearchResult]]:
        """
        Use LLM to rank events based on comprehensive context:
        1. RAG semantic similarity scores
        2. User profile (location, favorites, dislikes)
        3. Distance calculations for each event

        The LLM applies nuanced reasoning about trade-offs between relevance,
        preferences, and proximity.

        Args:
            results: List of events from RAG search with scores
            profile: User profile with preferences and location

        Returns:
            Re-ranked list of results
        """
        if not results:
            return results

        log_info(
            "applying_llm_ranking",
            num_events=len(results),
            has_user_location=bool(profile.location),
        )

        # Get user coordinates for distance calculations
        user_coords = None
        if profile.location:
            user_coords = self.geocoder.geocode(profile.location)
            if user_coords:
                user_lat, user_lon = user_coords["lat"], user_coords["lon"]
                log_info(
                    "user_location_resolved",
                    location=profile.location,
                    coords=f"{user_lat},{user_lon}",
                )

        # Build comprehensive event context for LLM
        events_context = []
        for idx, result in enumerate(results):
            # Extract event details
            if isinstance(result, EventWithVenue):
                title = result.title
                description = result.description
                genres = result.genres
                artists = result.artists if hasattr(result, "artists") else []
                venue_name = result.venue.name
                venue_lat = result.venue.latitude
                venue_lon = result.venue.longitude
            else:  # SearchResult
                title = result.title
                description = result.description
                genres = result.genres
                artists = getattr(result, "artists", [])
                venue_name = result.venue_name
                venue_lat = result.venue_latitude
                venue_lon = result.venue_longitude

            rag_score = result.score if hasattr(result, "score") else 0.0

            # Calculate distance if possible
            distance_km = None
            if user_coords and venue_lat and venue_lon:
                distance_km = self.geocoder.calculate_distance(
                    user_lat, user_lon, venue_lat, venue_lon
                )

            events_context.append({
                "index": idx + 1,
                "title": title,
                "description": description[:250],
                "genres": genres,
                "artists": artists if artists else [],
                "venue": venue_name,
                "rag_score": round(rag_score, 3),
                "distance_km": round(distance_km, 2) if distance_km else "unknown",
            })

        # Build prompt with all context
        prompt = self._build_ranking_prompt(events_context, profile)

        try:
            log_info("calling_llm_for_ranking", num_events=len(results), backend=self.llm_backend)

            # Call LLM based on backend
            if self.llm_backend == "gemini":
                response = self.llm_client.generate_content(prompt)
                ranking_text = response.text.strip()
            else:  # ollama
                import requests
                response = requests.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                    },
                    timeout=30
                )
                response.raise_for_status()
                ranking_text = response.json()["response"].strip()

            log_info("llm_ranking_response", response=ranking_text[:200])

            # Parse ranking (expecting comma-separated numbers)
            import re
            ranking_indices = []
            for x in ranking_text.split(","):
                x = x.strip()
                # Extract first number found
                match = re.search(r"\d+", x)
                if match:
                    ranking_indices.append(int(match.group()) - 1)

            # Validate ranking
            if len(ranking_indices) == len(results) and set(ranking_indices) == set(range(len(results))):
                reranked = [results[i] for i in ranking_indices]
                
                # Get titles for logging (works for both EventWithVenue and SearchResult)
                def get_title(r):
                    return r.title[:50] if hasattr(r, "title") else "unknown"
                
                log_info(
                    "llm_ranking_applied",
                    original_top=get_title(results[0]),
                    reranked_top=get_title(reranked[0]),
                )
                return reranked
            else:
                log_error(
                    "llm_ranking_invalid",
                    expected=len(results),
                    got=len(ranking_indices),
                    indices=ranking_indices,
                    reason="Invalid ranking from LLM, using RAG score order",
                )
                results.sort(key=lambda x: getattr(x, "score", 0.0), reverse=True)
                return results

        except Exception as e:
            log_error("llm_ranking_failed", error=str(e), error_type=type(e).__name__)
            # Fallback to RAG score sorting
            results.sort(key=lambda x: getattr(x, "score", 0.0), reverse=True)
            return results

    def _build_ranking_prompt(
        self,
        events_context: List[dict],
        profile: "UserProfile",
    ) -> str:
        """
        Build comprehensive prompt with all ranking context.

        Args:
            events_context: List of event dictionaries with all details
            profile: User profile

        Returns:
            Formatted prompt string
        """
        # Format user profile
        profile_text = f"""User Profile:
- Location: {profile.location or 'Not specified'}
- Favorite genres: {', '.join(profile.favorite_genres) if profile.favorite_genres else 'None'}
- Favorite artists: {', '.join(profile.favorite_artists) if profile.favorite_artists else 'None'}
- Disliked genres: {', '.join(profile.disliked_genres) if profile.disliked_genres else 'None'}
"""

        # Format events
        events_text = "\n\n".join([
            f"""{e['index']}. {e['title']}
   Venue: {e['venue']}
   Genres: {', '.join(e['genres'][:3])}
   Artists: {', '.join(e['artists'][:2]) if e['artists'] else 'N/A'}
   RAG Score: {e['rag_score']} (semantic similarity to query)
   Distance: {e['distance_km']} km from user
   Description: {e['description']}"""
            for e in events_context
        ])

        prompt = f"""You are an expert art curator helping rank cultural events for a user.

{profile_text}

Events to rank:
{events_text}

Task: Rank these events from most to least relevant for this user.

Consider:
1. **User preferences**: Strongly favor favorite genres/artists, avoid disliked genres
2. **Query relevance**: The RAG score shows semantic similarity to what the user asked for
3. **Proximity**: Closer events are more convenient, but amazing events may be worth traveling for
4. **Balance**: Sometimes a slightly farther event matching favorites is better than a nearby event they'd dislike

Apply nuanced reasoning. For example:
- An event with a favorite genre 5km away might beat a neutral event 1km away
- Avoid disliked genres even if RAG score is high
- Very high RAG scores indicate strong query match - don't ignore them

Respond with ONLY a comma-separated list of event numbers in your preferred ranking order.
Example: 3, 1, 5, 2, 4

Your ranking:"""

        return prompt

    def format_recommendations(
        self,
        results: List[Union[EventWithVenue, SearchResult]],
        include_reasoning: bool = False,
    ) -> str:
        """
        Format recommendations into user-friendly text.

        Args:
            results: List of EventWithVenue or SearchResult objects
            include_reasoning: Whether to include why each event was recommended

        Returns:
            Formatted string with recommendations
        """
        if not results:
            return self._format_no_results_message()

        response_lines = [f"I found {len(results)} events that might interest you:\n"]

        for i, result in enumerate(results, 1):
            response_lines.append(f"{i}. **{result.title}** at {result.venue_name}")
            response_lines.append(f"   {result.description[:150]}...")
            response_lines.append(f"   📅 {result.start_date} to {result.end_date}")
            response_lines.append(f"   🎨 {', '.join(result.genres[:3])}")
            response_lines.append(f"   💰 {result.cost_range}")
            response_lines.append(f"   🔗 {result.url}\n")

            if include_reasoning and hasattr(result, "score"):
                response_lines.append(f"   (Match score: {result.score:.3f})\n")

        return "\n".join(response_lines)

    def _format_no_results_message(self) -> str:
        """
        Generate a helpful message when no results are found.

        Returns:
            User-friendly message with suggestions
        """
        return """I couldn't find any events matching your query. Here are some suggestions:

🎨 **Try broader terms**: Instead of "cubist sculpture", try "sculpture" or "modern art"
📍 **Expand your area**: Consider nearby neighborhoods
📅 **Check different dates**: Some events might be seasonal
❤️ **Tell me your preferences**: Say "I like contemporary art" to help me learn

Would you like me to search for something else?"""

    def process(self, message: A2AMessage) -> A2AMessage:
        """
        Process A2A protocol message.

        Args:
            message: Input A2A message

        Returns:
            Response A2A message
        """
        if message.message_type != MessageType.REQUEST:
            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                message_type=MessageType.ERROR,
                content={"error": "Only REQUEST messages supported"},
                correlation_id=message.correlation_id,
            )

        action = message.content.get("action")

        if action == "recommend":
            query = message.content.get("query")
            profile = message.content.get("profile")  # Could be dict or UserProfile
            k = message.content.get("k", 5)

            # Convert profile dict to UserProfile if needed
            if profile and isinstance(profile, dict):
                from memory.models import UserProfile
                profile = UserProfile(**profile)

            results = self.recommend(query=query, profile=profile, k=k)

            # Serialize results (works for both EventWithVenue and SearchResult)
            serialized_results = [
                {
                    "title": r.title,
                    "description": r.description,
                    "venue_name": r.venue_name if hasattr(r, "venue_name") else r.venue.name,
                }
                for r in results
            ]

            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                message_type=MessageType.RESPONSE,
                content={"recommendations": serialized_results},
                correlation_id=message.correlation_id,
            )

        else:
            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                message_type=MessageType.ERROR,
                content={"error": f"Unknown action: {action}"},
                correlation_id=message.correlation_id,
            )
