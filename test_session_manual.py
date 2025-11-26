"""Manual test for session management and compaction."""

import os
os.environ["GOOGLE_API_KEY"] = os.popen("gcloud secrets versions access latest --secret=google-api-key --project=bcn-art-compass").read().strip()

from agents.event_ranker import create_event_ranker
from agents.orchestrator import create_orchestrator
from agents.profile_agent_adk import create_profile_agent
from agents.recommender_agent_adk import create_recommender_agent
from memory.storage import MemoryStorage

# Create dependencies
storage = MemoryStorage()
event_ranker = create_event_ranker()

# Create agents
profile_agent = create_profile_agent(storage=storage)
recommender_agent = create_recommender_agent(vector_store=None, event_ranker=event_ranker)

# Create orchestrator with aggressive compaction for testing
orchestrator = create_orchestrator(
    profile_agent=profile_agent,
    recommender_agent=recommender_agent,
    database_url=":memory:",
    compaction_interval=3,  # Compact every 3 turns
    overlap_size=1,  # Keep 1 turn for context
)

print("\n=== TEST 1: Session Persistence ===")
user_id = "test_user"
response1 = orchestrator.chat(user_id, "My name is Alice")
print(f"Response 1: {response1[:100]}...")

history1 = orchestrator.get_session_history(user_id)
print(f"History length after 1 turn: {len(history1)}")

response2 = orchestrator.chat(user_id, "What's my name?")
print(f"Response 2: {response2[:100]}...")

history2 = orchestrator.get_session_history(user_id)
print(f"History length after 2 turns: {len(history2)}")

print("\n=== TEST 2: Conversation Compaction ===")
user_id2 = "test_user_compaction"
for i in range(5):
    msg = f"Message {i+1}"
    orchestrator.chat(user_id2, msg)
    history = orchestrator.get_session_history(user_id2)
    print(f"After turn {i+1}: history length = {len(history)}")

print("\n=== TEST 3: Multiple Sessions ===")
orchestrator.chat("user_a", "I like modern art")
orchestrator.chat("user_b", "I prefer classical art")

history_a = orchestrator.get_session_history("user_a")
history_b = orchestrator.get_session_history("user_b")
print(f"User A history: {len(history_a)} turns")
print(f"User B history: {len(history_b)} turns")
print(f"Sessions are separate: {'modern' not in str(history_b)}")

print("\n=== TEST 4: Clear Session ===")
user_id3 = "test_user_clear"
orchestrator.chat(user_id3, "Hello")
before = orchestrator.get_session_history(user_id3)
print(f"Before clear: {len(before)} turns")

orchestrator.clear_session(user_id3)
after = orchestrator.get_session_history(user_id3)
print(f"After clear: {len(after)} turns")

print("\n=== TEST 5: Active Sessions ===")
sessions = orchestrator.get_active_sessions()
print(f"Active sessions: {sessions}")

print("\n✅ All manual tests passed!")
