#!/usr/bin/env python3
"""
Pre-build ChromaDB vector store for Cloud Run deployment.

This script creates a ChromaDB index with embeddings that can be
included in the Docker image, avoiding the need for sentence-transformers
in production.
"""

import json
from pathlib import Path

import chromadb
import yaml
from chromadb.config import Settings


def load_events(data_dir: str = "data") -> list[dict]:
    """Load events from YAML file."""
    events_file = Path(data_dir) / "events.yaml"

    with open(events_file) as f:
        data = yaml.safe_load(f)

    return data.get("events", [])


def create_searchable_text(event: dict) -> str:
    """Create searchable text from event data."""
    parts = [
        event.get("title", ""),
        event.get("description", ""),
        ", ".join(event.get("genres", [])),
        ", ".join(event.get("artists", [])),
    ]
    return " ".join(filter(None, parts))


def build_chromadb_index(
    events: list[dict],
    embeddings_file: str = "generated/vertex_embeddings.jsonl",
    output_dir: str = "storage/chromadb",
):
    """
    Build ChromaDB index using pre-computed embeddings.

    Args:
        events: List of event dictionaries
        embeddings_file: Path to JSONL file with embeddings
        output_dir: Output directory for ChromaDB storage
    """
    print(f"Building ChromaDB index in {output_dir}...")

    # Load pre-computed embeddings
    embeddings_map = {}
    with open(embeddings_file) as f:
        for line in f:
            data = json.loads(line)
            embeddings_map[data["id"]] = data["embedding"]

    print(f"  Loaded {len(embeddings_map)} pre-computed embeddings")

    # Create ChromaDB client
    client = chromadb.PersistentClient(
        path=output_dir,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True,
        ),
    )

    # Delete existing collection if it exists
    try:
        client.delete_collection("events")
    except Exception:
        pass

    # Create collection
    collection = client.create_collection(
        name="events",
        metadata={"hnsw:space": "cosine"},
    )

    # Prepare documents
    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for event in events:
        event_id = event["id"]

        if event_id not in embeddings_map:
            print(f"  Warning: No embedding for {event_id}, skipping")
            continue

        ids.append(event_id)
        documents.append(create_searchable_text(event))
        embeddings.append(embeddings_map[event_id])

        # Create metadata
        metadata = {
            "title": event.get("title", ""),
            "venue_id": event.get("venue_id", ""),
            "start_date": event.get("start_date", ""),
            "end_date": event.get("end_date", ""),
        }

        # Add genres
        if event.get("genres"):
            metadata["genres"] = ",".join(event["genres"])

        # Add artists
        if event.get("artists"):
            metadata["artists"] = ",".join(event["artists"])

        metadatas.append(metadata)

    # Add to collection
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(f"✓ Added {len(ids)} events to ChromaDB")
    print(f"✓ Index saved to {output_dir}")


def main():
    """Main execution."""
    print("=" * 60)
    print("ChromaDB Index Builder for Cloud Run")
    print("=" * 60)
    print()

    # Check if embeddings file exists
    embeddings_file = "generated/vertex_embeddings.jsonl"
    if not Path(embeddings_file).exists():
        print(f"Error: {embeddings_file} not found")
        print()
        print("Run this first:")
        print("  uv run ./scripts/prepare_vertex_data.py")
        return 1

    # Load events
    events = load_events()
    print(f"✓ Loaded {len(events)} events")
    print()

    # Build index
    output_dir = "storage/chromadb"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    build_chromadb_index(events, embeddings_file, output_dir)
    print()
    print("Next steps:")
    print("1. This ChromaDB index will be included in the Docker image")
    print("2. Deploy with: ./scripts/deploy.sh bcn-art-compass europe-southwest1")
    print()

    return 0


if __name__ == "__main__":
    exit(main())
