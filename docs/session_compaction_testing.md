# Testing Session Management & Compaction

This document explains how to test the session management and compaction features implemented in the BCN Art Compass orchestrator.

## Features Implemented

✅ **Persistent Session Storage** - Uses `DatabaseSessionService` from Google ADK  
✅ **Automatic History Compaction** - Uses `EventsCompactionConfig` to manage conversation length  
✅ **Multi-Instance Support** - Sessions stored in database, not in-memory  
✅ **Configurable Parameters** - Control compaction_interval and overlap_size  

## Configuration

### Orchestrator Parameters

```python
orchestrator = create_orchestrator(
    profile_agent=profile_agent,
    recommender_agent=recommender_agent,
    database_url="sqlite:///sessions.db",  # Persistent storage
    compaction_interval=5,  # Compact every 5 turns
    overlap_size=2,  # Keep 2 turns for context
)
```

### Default Values

- **compaction_interval**: `5` - Number of conversation turns before compaction
- **overlap_size**: `2` - Number of previous turns to keep after compaction
- **database_url**: 
  - API: `sqlite:////tmp/sessions.db` (Cloud Run compatible)
  - CLI: `sqlite:///storage/sessions.db` (local persistence)

## Testing Methods

### 1. Unit Test - Verify Configuration

```bash
uv run python -c "
from agents.orchestrator import ADKOrchestrator
from google.adk.apps.app import EventsCompactionConfig
import inspect

# Check orchestrator has correct parameters
sig = inspect.signature(ADKOrchestrator.__init__)
params = list(sig.parameters.keys())
assert 'compaction_interval' in params
assert 'overlap_size' in params
print('✅ Orchestrator has compaction parameters')

# Check EventsCompactionConfig is available
config = EventsCompactionConfig(compaction_interval=3, overlap_size=1)
print(f'✅ EventsCompactionConfig works: interval={config.compaction_interval}, overlap={config.overlap_size}')
"
```

### 2. API Integration Test

```bash
# Run existing API tests (they test session persistence)
uv run pytest tests/test_api.py -v

# Specifically test chat endpoint (uses sessions)
uv run pytest tests/test_api.py::test_chat_endpoint -v
```

### 3. Interactive CLI Test

```bash
# Start the CLI
uv run python cli.py

# Have a multi-turn conversation
You: My name is Alice
Bot: [response]

You: What's my name?
Bot: [should remember "Alice"]

You: Tell me about Barcelona
Bot: [response]

# Continue for 5+ turns to trigger compaction
# History should be maintained with compaction
```

### 4. Manual API Test

```bash
# Start the API server
uv run uvicorn api.main:app --reload

# In another terminal, test with curl:
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "user_id": "test_user"}'

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What did I just say?", "user_id": "test_user"}'
```

## How Compaction Works

### Without Compaction
```
Turn 1: [user msg 1, model response 1]
Turn 2: [user msg 1, model response 1, user msg 2, model response 2]
Turn 3: [user msg 1, model response 1, user msg 2, model response 2, user msg 3, model response 3]
... (grows unbounded)
```

### With Compaction (interval=3, overlap=1)
```
Turn 1: [user msg 1, model response 1]
Turn 2: [user msg 1, model response 1, user msg 2, model response 2]
Turn 3: [user msg 1, model response 1, user msg 2, model response 2, user msg 3, model response 3]
Turn 4: [COMPACTED: user msg 3, model response 3, user msg 4, model response 4]  # Only keeps 1 previous turn
Turn 5: [user msg 3, model response 3, user msg 4, model response 4, user msg 5, model response 5]
Turn 6: [COMPACTED: user msg 5, model response 5, user msg 6, model response 6]
```

This prevents token limit issues while maintaining conversation context.

## Verification Checklist

- [ ] Orchestrator imports successfully
- [ ] EventsCompactionConfig imports from google.adk.apps.app
- [ ] create_orchestrator accepts compaction_interval and overlap_size
- [ ] DatabaseSessionService is initialized with events_compaction_config
- [ ] API tests pass (test_api.py)
- [ ] Multi-turn conversations maintain context
- [ ] Sessions persist across API restarts (when using file-based SQLite)

## Architecture

```
ADKOrchestrator
├── DatabaseSessionService (persistent across instances)
│   ├── Storage: SQLite database
│   ├── Compaction: EventsCompactionConfig(interval=5, overlap=2)
│   └── Methods: get_session_history(), clear_session(), get_active_sessions()
├── Profile Agent (mandatory, external initialization)
│   └── Tools: Created via create_profile_tools(storage) closure factory
└── Recommender Agent (mandatory, external initialization)
    └── Tools: Created via create_recommendation_tools(vector_store, ranker) closure factory
```

## Production Considerations

1. **Database Location**:
   - Cloud Run: Use `/tmp/` for writable storage
   - Local: Use `storage/` directory
   - Production: Consider Cloud SQL or Firestore

2. **Compaction Settings**:
   - Shorter conversations: `compaction_interval=3`, `overlap_size=1`
   - Longer context needs: `compaction_interval=10`, `overlap_size=3`
   - Balance between context preservation and token limits

3. **Multi-Instance Deployment**:
   - Sessions stored in database (not instance memory)
   - Multiple Cloud Run instances can share session state
   - No session affinity required

## Troubleshooting

### Issue: Sessions not persisting
**Solution**: Check `database_url` is set to a file path, not `:memory:`

### Issue: Context lost too quickly
**Solution**: Increase `overlap_size` parameter

### Issue: Token limit errors
**Solution**: Decrease `compaction_interval` to compact more frequently

### Issue: Import error for EventsCompactionConfig
**Solution**: Ensure `google-adk>=1.19.0` is installed and import from `google.adk.apps.app`

## References

- [Google ADK Sessions Documentation](https://ai.google.dev/adk/docs/sessions)
- [Kaggle 5 Days of AI - Day 3B: Agent Memory](https://www.kaggle.com/code/kaggle5daysofai/day-3b-agent-memory)
- [EventsCompactionConfig Source](https://github.com/google/agent-developer-kit)
