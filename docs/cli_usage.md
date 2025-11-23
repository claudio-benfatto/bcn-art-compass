# BCN Art Compass CLI

Interactive command-line interface for discovering cultural events in Barcelona.

## Quick Start

### Local Mode (Default)
Uses local ChromaDB with sentence-transformers embeddings:

```bash
# Initialize vector store (first time only)
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py

# Run CLI
PYTHONPATH=$PWD uv run python cli.py
```

### Vertex AI Mode (Cloud)
Uses Vertex AI Vector Search with Gemini embeddings:

```bash
# Setup authentication (first time only)
gcloud auth application-default login

# Run CLI with Vertex AI backend
./scripts/cli_vertex.sh
```

## Usage

Once the CLI starts:

1. **Enter your user ID** (or press Enter for default)
2. **Ask questions** like:
   - "Show me Picasso exhibitions"
   - "What contemporary art is on?"
   - "Find sculpture events"
   - "I love street art" (updates your preferences)
3. **Exit** with `quit`, `exit`, or Ctrl+C

## Examples

```
💬 You:
> show me picasso exhibitions

🤖 Assistant:
----------------------------------------------------------
I found 5 events that might interest you:

1. **Picasso: The Blue Period Revisited** at Museu Picasso
   An intimate exploration of Picasso's Blue Period through paintings...
   📅 2025-01-10 to 2025-05-20
   🎨 painting, modern art
   💰 €15–€20
   🔗 https://example.com/picasso-blue-period
...
```

## Configuration

The CLI automatically detects the environment based on:
- `USE_VERTEX_RAG=true` → Uses Vertex AI
- Default → Uses local ChromaDB

See `config.py` for full configuration options.

## Comparison

| Feature | Local Mode | Vertex AI Mode |
|---------|-----------|----------------|
| Setup | Initialize local DB | Authenticate with GCP |
| Speed | Fast (local) | Network latency |
| Cost | Free | Pay per query (~$0.001) |
| Data | 15 events locally | 15 events in cloud |
| Embeddings | sentence-transformers | Gemini API |
| Use Case | Development | Testing cloud deployment |
