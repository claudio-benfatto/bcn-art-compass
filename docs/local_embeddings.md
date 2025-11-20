# Zero-Cost Local Embeddings Integration

## Overview

Added support for **free local embeddings** using `sentence-transformers`, eliminating the need for Google API keys and associated costs during local development.

## Motivation

- **Cost Concerns**: Google's text-embedding-004 API costs ~$0.00001 per 1K characters. While inexpensive, it adds up during development with frequent re-indexing.
- **API Key Friction**: Requiring API keys creates barriers for contributors and new developers.
- **Local Development**: Developers should be able to run the full system locally without external dependencies.
- **Demo/Testing**: Free embeddings make it easy to demo and test without worrying about API quotas.

## Implementation

### Files Created

#### `rag/embeddings_local.py`
```python
class LocalEmbeddingGenerator:
    """Generate embeddings locally using sentence-transformers (free!)"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Downloads ~91 MB model once, caches locally
        self.model = SentenceTransformer(model_name)
    
    def generate_embedding(self, text: str) -> list[float]:
        # Returns 384-dimensional embedding
        ...
    
    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        # Batch processing with progress bar
        ...
```

### Files Modified

#### `rag/vector_store.py`
- Added `use_local_embeddings: bool = True` parameter to `__init__()`
- Auto-detects embedding generator based on `GOOGLE_API_KEY` environment variable
- Defaults to local embeddings (free) if no API key is set
- Falls back to Google API if key is available

#### `scripts/init_vector_store.py`
- Removed mandatory `GOOGLE_API_KEY` check
- Auto-detects which embedding generator to use
- Displays clear messages about which option is being used

#### `scripts/demo_rag.py`
- Removed mandatory `GOOGLE_API_KEY` check
- Auto-detects embedding option
- Shows embedding type in demo header

#### `agents/orchestrator.py`
- Updated to support `use_local_embeddings` parameter
- Auto-detects when no API key is present

#### `README.md`
- Added "Choose Your Embedding Option" section
- Created comparison table (cost, quality, speed, dimensions)
- Updated project structure to show `embeddings_local.py`

## Usage

### Auto-Detection (Default Behavior)

```bash
# No API key and no flag → Uses local embeddings (free)
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py

# API key present, no flag → Uses Google API embeddings
export GOOGLE_API_KEY='your-key-here'
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py
```

### Explicit Control with USE_LOCAL_EMBEDDINGS Flag

For development flexibility, you can force a specific embedding option:

```bash
# Force local embeddings (even if API key is set)
export USE_LOCAL_EMBEDDINGS=true
export GOOGLE_API_KEY='your-key-here'  # Will be ignored
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py

# Force Google API embeddings (requires API key)
export USE_LOCAL_EMBEDDINGS=false
export GOOGLE_API_KEY='your-key-here'
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py
```

### Priority Order

The system determines which embeddings to use in this order:

1. **Explicit parameter**: `VectorStore(use_local_embeddings=True/False)`
2. **USE_LOCAL_EMBEDDINGS** environment variable (`true`/`false`/`1`/`0`/`yes`/`no`)
3. **Auto-detection**: Presence of `GOOGLE_API_KEY` (key exists → Google API, no key → Local)

This gives developers maximum flexibility during development and testing.

### Decision Matrix

| GOOGLE_API_KEY | USE_LOCAL_EMBEDDINGS | Result |
|----------------|---------------------|--------|
| ❌ Not set | ❌ Not set | **Local** (default) |
| ✅ Set | ❌ Not set | **Google API** (auto-detect) |
| ❌ Not set | `true` | **Local** |
| ✅ Set | `true` | **Local** (forced) |
| ❌ Not set | `false` | **Error** (no API key) |
| ✅ Set | `false` | **Google API** (forced) |

### Common Development Scenarios

**Scenario 1: New developer, no API key**
```bash
# Just works with free local embeddings!
uv sync
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py
```

**Scenario 2: Developer with API key, wants to test both**
```bash
# Test with local embeddings (free, fast iteration)
USE_LOCAL_EMBEDDINGS=true PYTHONPATH=$PWD uv run python scripts/init_vector_store.py

# Test with Google API (production-like quality)
USE_LOCAL_EMBEDDINGS=false PYTHONPATH=$PWD uv run python scripts/init_vector_store.py
```

**Scenario 3: CI/CD pipeline (wants consistency)**
```bash
# Always use local in CI (fast, no API costs)
USE_LOCAL_EMBEDDINGS=true PYTHONPATH=$PWD uv run python scripts/init_vector_store.py
```

## Technical Details

### Model Comparison

| Feature | Local (all-MiniLM-L6-v2) | Google (text-embedding-004) |
|---------|--------------------------|----------------------------|
| **Dimensions** | 384 | 768 |
| **Cost** | Free | ~$0.00001 per 1K chars |
| **Download Size** | ~91 MB (one-time) | None |
| **Speed** | Fast (local CPU) | Network-dependent |
| **Quality** | Good for demos/dev | Production-grade |
| **Model Size** | 22M parameters | Unknown (larger) |

### Why all-MiniLM-L6-v2?

1. **Small and Fast**: 91 MB download, runs on CPU
2. **Good Quality**: Competitive performance on semantic similarity tasks
3. **Well-Tested**: 73M+ downloads on HuggingFace
4. **Purpose-Built**: Optimized for sentence embeddings
5. **384 Dimensions**: Good balance of quality and speed

### Architecture Pattern

The embedding generators follow a **strategy pattern**:
- Both implement the same interface (`generate_embedding`, `generate_embeddings_batch`)
- `VectorStore` accepts either generator type
- Selection happens at initialization based on environment
- Zero changes needed in downstream code (orchestrator, tools, API)

## Testing

All 19 core tests pass without requiring any API key:

```bash
uv run pytest -v
# 19 passed, 5 skipped (optional embedding tests)
```

To run optional embedding/vector store tests:
```bash
export GOOGLE_API_KEY='your-key'
uv run pytest -v --run-embedding-tests
# 24 passed
```

## Performance

### Initialization
- **First Run**: ~6-7 seconds (downloads model)
- **Subsequent Runs**: ~2-3 seconds (cached model)

### Embedding Generation
- **15 events batch**: ~1 second
- **Per-query embedding**: ~200ms

This is fast enough for local development and demos. Production deployments can use Google API for better quality.

## Migration Path

For existing users with Google API keys:

1. **No Action Needed**: System still uses Google embeddings if `GOOGLE_API_KEY` is set
2. **Want Local**: Simply unset `GOOGLE_API_KEY` and re-run `init_vector_store.py`
3. **Want Both**: Initialize two different collections (not implemented yet)

## Future Enhancements

Potential improvements for later:

1. **Model Selection**: Allow users to choose different local models via config
2. **Hybrid Mode**: Use local for dev, Google for prod (environment-based config)
3. **Quantization**: Use int8 quantized models for even faster local inference
4. **GPU Support**: Detect CUDA/MPS and use GPU if available
5. **Batch Caching**: Cache embeddings to avoid re-computing unchanged events

## Impact

### Before
```bash
# Required for everything
export GOOGLE_API_KEY='your-key-here'
# Costs accumulated with every re-index
```

### After
```bash
# Works out of the box, zero cost!
uv run python scripts/init_vector_store.py
```

### Benefits
- ✅ **Zero Cost**: No API charges for local development
- ✅ **Zero Friction**: New contributors can start immediately
- ✅ **Offline Capable**: Works without internet after initial model download
- ✅ **Faster Iteration**: No API latency, no rate limits
- ✅ **Production Ready**: Google API still available when needed

## Observability

All embedding operations are logged with structured logging:

```json
{"event": "using_local_embeddings", "model": "sentence-transformers"}
{"event": "loading_local_embedding_model", "model": "all-MiniLM-L6-v2"}
{"event": "local_embedding_model_loaded", "model": "all-MiniLM-L6-v2"}
{"event": "generating_local_embeddings_batch", "num_texts": 15}
{"event": "local_embeddings_batch_complete", "total": 15, "successful": 15}
```

This helps debug issues and understand which embedding option is being used.

## Conclusion

The local embeddings integration provides:
1. **MVP-Friendly**: Zero cost aligns with 2-week MVP goals
2. **Developer-Friendly**: No API keys needed to get started
3. **Production Path**: Google API option still available
4. **Clean Architecture**: Strategy pattern makes swapping embeddings trivial

The system now truly runs both locally (free) and in the cloud (optional paid), fulfilling the MVP requirement.
