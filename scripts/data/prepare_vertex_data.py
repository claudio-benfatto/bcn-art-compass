#!/usr/bin/env python3
"""
Prepare event data for Vertex AI Vector Search.

Generates embeddings for all events and exports to JSONL format
required by Vertex AI.
"""

import json
import os
from pathlib import Path

import google.generativeai as genai
import yaml

# Configure Gemini API
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("Error: GOOGLE_API_KEY environment variable not set")
    exit(1)

genai.configure(api_key=api_key)


def load_events(data_dir: str = "data") -> list[dict]:
    """Load events from YAML file."""
    events_file = Path(data_dir) / "events.yaml"
    
    with open(events_file) as f:
        data = yaml.safe_load(f)
    
    return data.get("events", [])


def generate_embedding(text: str) -> list[float]:
    """Generate embedding using Gemini API."""
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_document",
    )
    return result["embedding"]


def create_searchable_text(event: dict) -> str:
    """Create searchable text from event data."""
    parts = [
        event.get("title", ""),
        event.get("description", ""),
        ", ".join(event.get("genres", [])),
        ", ".join(event.get("artists", [])),
    ]
    return " ".join(filter(None, parts))


def prepare_vertex_ai_data(events: list[dict], output_file: str = "generated/vertex_embeddings.jsonl"):
    """
    Prepare data for Vertex AI Vector Search.
    
    Format: One JSON object per line with 'id', 'embedding', and 'restricts' fields.
    """
    print(f"Processing {len(events)} events...")
    
    with open(output_file, "w") as f:
        for i, event in enumerate(events):
            # Create searchable text
            text = create_searchable_text(event)
            
            # Generate embedding
            print(f"  [{i+1}/{len(events)}] Generating embedding for: {event['title'][:50]}...")
            embedding = generate_embedding(text)
            
            # Create Vertex AI format
            # Vertex AI expects: id, embedding, and optional restricts/crowding_tag
            vertex_data = {
                "id": event["id"],
                "embedding": embedding,
            }
            
            # Add restricts for filtering (optional but recommended)
            if event.get("genres") or event.get("venue_id"):
                restricts = []
                if event.get("genres"):
                    restricts.append({"namespace": "genre", "allow": event["genres"]})
                if event.get("venue_id"):
                    restricts.append({"namespace": "venue", "allow": [event["venue_id"]]})
                vertex_data["restricts"] = restricts
            
            # Write as JSONL
            f.write(json.dumps(vertex_data) + "\n")
    
    print(f"\n✓ Embeddings saved to {output_file}")
    print(f"  Total records: {len(events)}")
    print(f"  Embedding dimensions: {len(embedding)}")


def main():
    """Main execution."""
    print("=" * 60)
    print("Vertex AI Vector Search - Data Preparation")
    print("=" * 60)
    print()
    
    # Load events
    events = load_events()
    print(f"✓ Loaded {len(events)} events")
    print()
    
    # Generate embeddings and export
    prepare_vertex_ai_data(events)
    print()
    print("Next steps:")
    print("1. Upload generated/vertex_embeddings.jsonl to Google Cloud Storage")
    print("2. Create Vertex AI Vector Search index")
    print("3. Deploy the index to an endpoint")
    print()
    print("Run: ./scripts/setup_vertex_ai.sh")


if __name__ == "__main__":
    main()
