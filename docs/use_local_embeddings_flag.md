# USE_LOCAL_EMBEDDINGS Flag Implementation

## Summary

Added `USE_LOCAL_EMBEDDINGS` environment variable flag to give developers explicit control over which embedding generator to use, even when a Google API key is present.

## Motivation

Developers needed the ability to:
1. **Test both options**: Compare local vs Google API embeddings side-by-side
2. **Force local in CI/CD**: Use free embeddings in automated pipelines regardless of API key presence
3. **Quick switching**: Toggle between options without unsetting environment variables

## Implementation

### Environment Variable

```bash
USE_LOCAL_EMBEDDINGS=true   # Force local embeddings
USE_LOCAL_EMBEDDINGS=false  # Force Google API embeddings
# (not set)                 # Auto-detect based on GOOGLE_API_KEY
```

Accepts: `true`, `false`, `1`, `0`, `yes`, `no` (case-insensitive)

### Priority Order

1. **Explicit parameter**: `VectorStore(use_local_embeddings=True/False)`
2. **USE_LOCAL_EMBEDDINGS** env var
3. **Auto-detection**: Presence of `GOOGLE_API_KEY`

### Files Modified

- `rag/vector_store.py`: Added flag detection logic in `__init__()`
- `scripts/init_vector_store.py`: Check flag before API key
- `scripts/demo_rag.py`: Check flag before API key
- `agents/orchestrator.py`: Pass-through support, let VectorStore handle it
- `README.md`: Added "Explicit Control via Flag" section
- `docs/local_embeddings.md`: Added usage examples and decision matrix

### Files Created

- `scripts/test_flag.py`: Comprehensive test of all flag scenarios

## Usage Examples

### Force Local (Even with API Key)

```bash
export GOOGLE_API_KEY='your-key-here'
export USE_LOCAL_EMBEDDINGS=true
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py
# → Uses local embeddings (free)
```

### Force Google API

```bash
export GOOGLE_API_KEY='your-key-here'
export USE_LOCAL_EMBEDDINGS=false
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py
# → Uses Google API embeddings
```

### Compare Both

```bash
export GOOGLE_API_KEY='your-key-here'

# Create local index
USE_LOCAL_EMBEDDINGS=true PYTHONPATH=$PWD uv run python scripts/init_vector_store.py

# Query with local
USE_LOCAL_EMBEDDINGS=true PYTHONPATH=$PWD uv run python scripts/demo_rag.py

# Now try Google API
USE_LOCAL_EMBEDDINGS=false PYTHONPATH=$PWD uv run python scripts/init_vector_store.py
USE_LOCAL_EMBEDDINGS=false PYTHONPATH=$PWD uv run python scripts/demo_rag.py
```

## Decision Matrix

| GOOGLE_API_KEY | USE_LOCAL_EMBEDDINGS | Result |
|----------------|---------------------|--------|
| ❌ Not set | ❌ Not set | **Local** (default) |
| ✅ Set | ❌ Not set | **Google API** (auto-detect) |
| ❌ Not set | `true` | **Local** |
| ✅ Set | `true` | **Local** (forced) |
| ❌ Not set | `false` | **Error** (no API key) |
| ✅ Set | `false` | **Google API** (forced) |

## Testing

All 5 flag scenarios tested and passing:

```bash
PYTHONPATH=$PWD uv run python scripts/test_flag.py
```

Results:
- ✅ No flag + no API key → Local
- ✅ Flag forces local (even with API key)
- ✅ Flag forces Google API (with key)
- ✅ API key + no flag → Google API (auto-detect)
- ✅ Explicit parameter overrides env vars

## Benefits

1. **Development Flexibility**: Test both options without reconfiguring
2. **CI/CD Control**: Lock embedding choice in automated pipelines
3. **Cost Management**: Force local in dev, Google in prod
4. **A/B Testing**: Easy comparison of embedding quality
5. **Backwards Compatible**: Auto-detection still works if flag not set

## Example Workflow

```bash
# Developer has API key but wants to develop with free local embeddings
export GOOGLE_API_KEY='your-key'
export USE_LOCAL_EMBEDDINGS=true

# Develop with local (fast, free)
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py
PYTHONPATH=$PWD uv run python scripts/demo_rag.py

# Before committing, test with production embeddings
export USE_LOCAL_EMBEDDINGS=false
PYTHONPATH=$PWD uv run python scripts/init_vector_store.py
PYTHONPATH=$PWD uv run python scripts/demo_rag.py

# Verify quality difference is acceptable
# Commit code knowing it works with both options
```

## Observability

All choices are logged:

```json
{"embedding_type": "local (forced by flag)", ...}
{"embedding_type": "Google API (forced by flag)", ...}
{"embedding_type": "local (no API key)", ...}
{"embedding_type": "Google API (auto-detected)", ...}
```

This helps debug which embedding option is being used and why.
