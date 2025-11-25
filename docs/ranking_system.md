# Event Ranking System

## Overview

The RecommenderAgent uses a comprehensive ranking system that considers **three factors** to provide personalized event recommendations:

1. **User Query** - What the user is specifically asking for (immediate intent)
2. **User Profile** - Long-term preferences, favorites, and dislikes
3. **Location** - Geographic proximity to the user

## Architecture

```
User Query: "sculpture exhibitions"
     ↓
VectorStore.query() → RAG semantic search → Initial results with scores
     ↓
EventRanker.rank_events(results, profile, user_query)
     ↓
LLM evaluates ALL THREE factors:
  - Query intent ("sculpture exhibitions")
  - Profile (favorite_genres: ["sculpture", "contemporary"])
  - Location (distance from Barcelona)
     ↓
Re-ranked results optimized for user
```

## How It Works

### Step 1: Semantic Search (RAG)

The vector store performs semantic similarity search based on the user's query:

```python
# In RecommenderAgent.recommend()
results = self.vector_store.query(
    query,              # "sculpture exhibitions"
    k=k,
    profile=profile,
    filters=filters,
)
```

Each result gets a **RAG score** (0.0-1.0) indicating semantic similarity to the query.

### Step 2: LLM-Based Re-ranking

The EventRanker passes comprehensive context to an LLM (Gemini or Ollama):

```python
# In EventRanker.rank_events()
results = self.event_ranker.rank_events(
    results,      # RAG results with scores
    profile,      # User preferences and location
    user_query    # Original query
)
```

### Step 3: LLM Reasoning

The LLM receives a detailed prompt with:

```
User Query: "sculpture exhibitions"

User Profile:
- Location: Barcelona
- Favorite genres: sculpture, contemporary
- Favorite artists: None
- Disliked genres: video art

Events to rank:
1. Contemporary Sculpture Exhibition
   Venue: Gallery A
   Genres: sculpture, contemporary
   RAG Score: 0.85 (semantic similarity to query)
   Distance: 1.5 km from user
   Description: Modern sculptures from local artists

2. Installation Art Show
   Venue: Gallery C
   Genres: video art, installation
   RAG Score: 0.90 (semantic similarity to query)
   Distance: 0.8 km from user
   Description: Immersive video art installations

3. Painting Workshop
   Venue: Gallery B
   Genres: painting, workshop
   RAG Score: 0.75 (semantic similarity to query)
   Distance: 3.2 km from user
   Description: Learn oil painting techniques
```

**Prompt Instructions:**
```
Task: Rank these events from most to least relevant for this user.

Consider ALL THREE factors:
1. **User query**: What is the user specifically looking for? This is their immediate intent.
2. **User preferences**: Favor favorite genres/artists, avoid disliked genres (long-term profile)
3. **Location**: Closer events are more convenient, but amazing matches may be worth traveling for
4. **RAG score**: Shows semantic similarity between the event and the user's query

Apply nuanced reasoning. For example:
- If user asks "sculpture exhibitions", prioritize sculpture events even if farther away
- An event matching the query + favorite genre beats one that only matches profile
- Avoid disliked genres even if they match the query
- Balance query intent with profile preferences and location
- Very high RAG scores indicate strong query-event match - weight them heavily
```

**Example LLM Response:**
```
1, 3, 2
```

This ranking means:
- **Event 1** (Sculpture) - Matches query + favorite genre, even though slightly lower RAG score
- **Event 3** (Painting) - Neutral, decent RAG score
- **Event 2** (Video art) - Highest RAG score BUT disliked genre = ranked last

## Ranking Logic

The LLM applies sophisticated reasoning:

### Query-First Approach
If user asks "sculpture exhibitions", sculpture events get priority regardless of distance or profile.

### Profile Enhancement
Among events matching the query, user preferences provide fine-tuning:
- Favorite genres get boosted
- Disliked genres get penalized (even with high RAG scores)
- Favorite artists mentioned = significant boost

### Location Consideration
- Close events (< 2km) get slight preference
- Amazing matches worth traveling for (e.g., favorite artist's exhibition)
- Very far events (> 20km) need exceptional match to rank high

### RAG Score Weight
High RAG scores (> 0.85) indicate strong semantic match and are weighted heavily, unless contradicted by strong profile signals.

## Benefits

### 1. Intent-Aware
Unlike pure semantic search, the system understands **why** the user is asking:
- "sculpture exhibitions" → Prioritize sculpture
- "free events nearby" → Prioritize cost + location
- "Picasso exhibitions" → Prioritize specific artist

### 2. Personalized
The system learns from user profile:
- If user loves contemporary art, contemporary events rank higher
- If user dislikes video art, those events rank lower
- Location preferences considered

### 3. Context-Balanced
The LLM balances competing factors:
- Query intent vs. profile preferences
- Semantic relevance vs. geographic proximity
- User favorites vs. discovering new genres

### 4. Explainable
The ranking is based on clear factors that can be explained to users:
> "I ranked the Contemporary Sculpture Exhibition first because it matches your query, is in your favorite genre (sculpture), and is only 1.5km away."

## Implementation Details

### EventRanker Interface

```python
class EventRanker(ABC):
    @abstractmethod
    def rank_events(
        self,
        results: List[SearchResult],
        profile: UserProfile,
        user_query: str = "",
    ) -> List[SearchResult]:
        """Rank events based on query, profile, and location."""
        pass
```

### Two Implementations

1. **GeminiEventRanker** - Uses Google Gemini (gemini-2.5-flash)
   - Production deployment on Cloud Run
   - Requires GOOGLE_API_KEY

2. **OllamaEventRanker** - Uses local Ollama (llama3.1:8b)
   - Local development
   - No API key required

### Factory Pattern

```python
def create_event_ranker(api_key: Optional[str] = None) -> EventRanker:
    """Create appropriate ranker based on environment."""
    if api_key:
        return GeminiEventRanker(api_key)
    else:
        return OllamaEventRanker()
```

## Testing

The system includes comprehensive tests:

```python
# tests/test_recommender_with_query.py

def test_recommender_uses_query_profile_location():
    """Verify all three factors are passed to ranker."""
    # Asserts that query, profile, and results are all provided

def test_ranking_considers_query_and_profile():
    """Verify LLM balances query intent with profile."""
    # User asks for sculpture (matches profile)
    # Sculpture ranks first even with lower RAG score

def test_recommender_without_profile_skips_ranking():
    """Without profile, fall back to RAG scores only."""
    # Uses pure semantic similarity
```

## Example Scenarios

### Scenario 1: Query Matches Profile
```
Query: "contemporary sculpture exhibitions"
Profile: favorite_genres = ["sculpture", "contemporary"]
Result: Strong boost - query + profile aligned
```

### Scenario 2: Query Contradicts Profile
```
Query: "video art installations"
Profile: disliked_genres = ["video art"]
Result: Moderate ranking - respect query intent but user may not enjoy
```

### Scenario 3: Location-Sensitive Query
```
Query: "art exhibitions near me"
Profile: location = "Barcelona"
Result: Distance heavily weighted, close events prioritized
```

### Scenario 4: Artist-Specific Query
```
Query: "Picasso exhibitions"
Profile: favorite_artists = ["Picasso"]
Result: Extreme boost - query + favorite artist
```

## Future Enhancements

1. **Time-Based Ranking** - Prioritize events happening soon
2. **Popularity Signals** - Consider crowd-sourced ratings
3. **Collaborative Filtering** - "Users like you also enjoyed..."
4. **Multi-Modal Ranking** - Include event images in LLM context
5. **Explanation Generation** - Have LLM explain each ranking decision
6. **A/B Testing** - Compare different ranking strategies
7. **Feedback Loop** - Learn from user clicks and attendance

## Observability

The system logs detailed ranking information:

```json
{
  "event": "applying_llm_ranking",
  "num_events": 5,
  "backend": "gemini",
  "has_user_location": true
}

{
  "event": "llm_ranking_applied",
  "original_top": "Installation Art Show",
  "reranked_top": "Contemporary Sculpture Exhibition"
}
```

This enables monitoring and debugging of ranking decisions in production.

## Conclusion

The ranking system provides a sophisticated, multi-factor approach to event recommendations that:

✅ Respects user's immediate query intent  
✅ Personalizes based on long-term profile  
✅ Considers geographic convenience  
✅ Balances competing signals intelligently  
✅ Works locally (Ollama) and in production (Gemini)  
✅ Is fully tested and observable  

This creates a recommendation experience that feels both relevant and personalized, adapting to both what users ask for right now and what they've enjoyed in the past.
