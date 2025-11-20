"""
Unit tests for RAG components.
"""

import pytest

from rag.data_loader import load_events, load_events_with_venues, load_venues
from rag.embeddings import EmbeddingGenerator
from rag.models import Event, EventWithVenue, Venue
from rag.vector_store import VectorStore


@pytest.mark.unit
def test_load_events():
    """Test loading events from YAML file."""
    events = load_events()

    assert len(events) > 0
    assert all(isinstance(event, Event) for event in events)
    assert all(hasattr(event, "id") for event in events)
    assert all(hasattr(event, "title") for event in events)


@pytest.mark.unit
def test_load_venues():
    """Test loading venues from YAML file."""
    venues = load_venues()

    assert len(venues) > 0
    assert all(isinstance(venue, Venue) for venue in venues)
    assert all(hasattr(venue, "id") for venue in venues)
    assert all(hasattr(venue, "name") for venue in venues)


@pytest.mark.unit
def test_load_events_with_venues():
    """Test loading events joined with venues."""
    events_with_venues = load_events_with_venues()

    assert len(events_with_venues) > 0
    assert all(isinstance(ewv, EventWithVenue) for ewv in events_with_venues)
    assert all(isinstance(ewv.event, Event) for ewv in events_with_venues)
    assert all(isinstance(ewv.venue, Venue) for ewv in events_with_venues)


@pytest.mark.unit
def test_event_with_venue_to_text():
    """Test conversion of EventWithVenue to searchable text."""
    events_with_venues = load_events_with_venues()
    assert len(events_with_venues) > 0

    text = events_with_venues[0].to_text()

    # Check that text contains key information
    assert events_with_venues[0].event.title in text
    assert events_with_venues[0].venue.name in text
    assert any(genre in text for genre in events_with_venues[0].event.genres)


@pytest.mark.unit
def test_embedding_generator_single(request):
    """Test generating a single embedding."""
    if not request.config.getoption("--run-embedding-tests"):
        pytest.skip("Embedding tests require API key. Use --run-embedding-tests to enable.")

    generator = EmbeddingGenerator()
    text = "Contemporary sculpture exhibition at MACBA"

    embedding = generator.generate_embedding(text)

    assert isinstance(embedding, list)
    assert len(embedding) > 0
    assert all(isinstance(val, float) for val in embedding)


@pytest.mark.unit
def test_embedding_generator_batch(request):
    """Test generating embeddings for multiple texts."""
    if not request.config.getoption("--run-embedding-tests"):
        pytest.skip("Embedding tests require API key.")

    generator = EmbeddingGenerator()
    texts = [
        "Contemporary art exhibition",
        "Sculpture at MACBA",
        "Picasso museum collection",
    ]

    embeddings = generator.generate_embeddings_batch(texts)

    assert len(embeddings) == len(texts)
    assert all(isinstance(emb, list) for emb in embeddings)
    assert all(len(emb) > 0 for emb in embeddings)


@pytest.mark.unit
def test_embedding_generator_query(request):
    """Test generating embedding for a search query."""
    if not request.config.getoption("--run-embedding-tests"):
        pytest.skip("Embedding tests require API key.")

    generator = EmbeddingGenerator()
    query = "Show me contemporary art exhibitions"

    embedding = generator.generate_query_embedding(query)

    assert isinstance(embedding, list)
    assert len(embedding) > 0


@pytest.fixture
def test_vector_store():
    """Create a test vector store."""
    # Use a separate test collection
    store = VectorStore(collection_name="test_events")
    yield store
    # Cleanup after test
    store.clear()


@pytest.mark.unit
def test_vector_store_add_and_query(test_vector_store, request):
    """Test adding documents and querying the vector store."""
    if not request.config.getoption("--run-embedding-tests"):
        pytest.skip("Vector store tests require API key.")

    # Load a few events
    events_with_venues = load_events_with_venues()[:3]  # Just use first 3 for testing

    # Add to vector store
    test_vector_store.add_documents(events_with_venues)

    # Check documents were added
    assert test_vector_store.count() == 3

    # Query
    results = test_vector_store.query("contemporary sculpture", k=2)

    assert len(results) > 0
    assert all(hasattr(result, "title") for result in results)
    assert all(hasattr(result, "score") for result in results)
    assert all(result.score > 0 for result in results)


@pytest.mark.unit
def test_vector_store_clear(test_vector_store, request):
    """Test clearing the vector store."""
    if not request.config.getoption("--run-embedding-tests"):
        pytest.skip("Vector store tests require API key.")

    events_with_venues = load_events_with_venues()[:2]
    test_vector_store.add_documents(events_with_venues)

    assert test_vector_store.count() == 2

    test_vector_store.clear()

    assert test_vector_store.count() == 0
