"""
Quick test script to verify USE_LOCAL_EMBEDDINGS flag works correctly.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.vector_store import VectorStore


def test_flag():
    """Test the USE_LOCAL_EMBEDDINGS flag."""
    
    print("\n" + "=" * 60)
    print("Testing USE_LOCAL_EMBEDDINGS Flag")
    print("=" * 60 + "\n")
    
    # Test 1: Default behavior (no flag, no API key)
    print("Test 1: No flag, no API key")
    os.environ.pop("USE_LOCAL_EMBEDDINGS", None)
    os.environ.pop("GOOGLE_API_KEY", None)
    vs1 = VectorStore()
    print(f"✅ Result: {type(vs1.embedding_generator).__name__}")
    assert "Local" in type(vs1.embedding_generator).__name__
    print()
    
    # Test 2: Flag forces local
    print("Test 2: Flag forces local (USE_LOCAL_EMBEDDINGS=true)")
    os.environ["USE_LOCAL_EMBEDDINGS"] = "true"
    os.environ["GOOGLE_API_KEY"] = "fake-key"  # Even with key, should use local
    vs2 = VectorStore()
    print(f"✅ Result: {type(vs2.embedding_generator).__name__}")
    assert "Local" in type(vs2.embedding_generator).__name__
    print()
    
    # Test 3: Flag forces Google API
    print("Test 3: Flag forces Google API (USE_LOCAL_EMBEDDINGS=false)")
    os.environ["USE_LOCAL_EMBEDDINGS"] = "false"
    os.environ["GOOGLE_API_KEY"] = "fake-key"
    vs3 = VectorStore()
    print(f"✅ Result: {type(vs3.embedding_generator).__name__}")
    assert "Embedding" in type(vs3.embedding_generator).__name__
    assert "Local" not in type(vs3.embedding_generator).__name__
    print()
    
    # Test 4: API key without flag (auto-detect)
    print("Test 4: API key present, no flag (auto-detects Google API)")
    os.environ.pop("USE_LOCAL_EMBEDDINGS", None)
    os.environ["GOOGLE_API_KEY"] = "fake-key"
    vs4 = VectorStore()
    print(f"✅ Result: {type(vs4.embedding_generator).__name__}")
    assert "Embedding" in type(vs4.embedding_generator).__name__
    assert "Local" not in type(vs4.embedding_generator).__name__
    print()
    
    # Test 5: Explicit parameter overrides everything
    print("Test 5: Explicit parameter (use_local_embeddings=True)")
    os.environ["USE_LOCAL_EMBEDDINGS"] = "false"
    os.environ["GOOGLE_API_KEY"] = "fake-key"
    vs5 = VectorStore(use_local_embeddings=True)
    print(f"✅ Result: {type(vs5.embedding_generator).__name__}")
    assert "Local" in type(vs5.embedding_generator).__name__
    print()
    
    print("=" * 60)
    print("All tests passed! 🎉")
    print("=" * 60 + "\n")
    
    print("Summary:")
    print("  1. No flag + no API key → Local embeddings")
    print("  2. USE_LOCAL_EMBEDDINGS=true → Local (even with API key)")
    print("  3. USE_LOCAL_EMBEDDINGS=false + API key → Google API")
    print("  4. API key + no flag → Google API (auto-detect)")
    print("  5. use_local_embeddings parameter → Overrides all env vars")
    print()


if __name__ == "__main__":
    test_flag()
