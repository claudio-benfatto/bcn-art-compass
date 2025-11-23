"""
Cloud configuration management for BCN Art Compass.

Auto-detects local vs cloud environments and provides appropriate settings.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppConfig:
    """
    Application configuration.
    
    Auto-detects environment and provides appropriate settings.
    """
    
    # Environment detection
    is_cloud: bool
    environment: str  # "local", "cloud_run", "vertex_ai"
    
    # Storage backends
    use_firestore: bool
    use_vertex_rag: bool
    
    # GCP settings
    project_id: Optional[str]
    location: str
    
    # RAG settings
    vector_store_path: str
    vector_store_collection: str
    
    # Memory settings
    firestore_collection: str
    local_storage_path: str
    
    # LLM settings
    use_local_llm: bool
    local_model: str
    
    @classmethod
    def from_env(cls) -> "AppConfig":
        """
        Create configuration from environment variables.
        
        Auto-detects:
        - Cloud Run (K_SERVICE environment variable)
        - Vertex AI (VERTEX_AI_ENVIRONMENT variable)
        - Local development (default)
        
        Returns:
            AppConfig: Configuration instance
        """
        # Detect environment
        is_cloud_run = os.getenv("K_SERVICE") is not None
        is_vertex = os.getenv("VERTEX_AI_ENVIRONMENT") is not None
        is_cloud = is_cloud_run or is_vertex
        
        if is_cloud_run:
            environment = "cloud_run"
        elif is_vertex:
            environment = "vertex_ai"
        else:
            environment = "local"
        
        # Storage backends
        # Use cloud storage in cloud environments unless explicitly disabled
        use_firestore = os.getenv("USE_FIRESTORE", str(is_cloud)).lower() == "true"
        use_vertex_rag = os.getenv("USE_VERTEX_RAG", "false").lower() == "true"
        
        # GCP settings
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        
        # RAG settings
        vector_store_path = os.getenv("VECTOR_STORE_PATH", "storage/chroma_db")
        vector_store_collection = os.getenv("VECTOR_STORE_COLLECTION", "events")
        
        # Memory settings
        firestore_collection = os.getenv("FIRESTORE_COLLECTION", "user_profiles")
        local_storage_path = os.getenv("LOCAL_STORAGE_PATH", "storage/user_profiles.json")
        
        # LLM settings
        use_local_llm = os.getenv("USE_LOCAL_LLM", str(not is_cloud)).lower() == "true"
        local_model = os.getenv("LOCAL_MODEL", "llama3.2")
        
        return cls(
            is_cloud=is_cloud,
            environment=environment,
            use_firestore=use_firestore,
            use_vertex_rag=use_vertex_rag,
            project_id=project_id,
            location=location,
            vector_store_path=vector_store_path,
            vector_store_collection=vector_store_collection,
            firestore_collection=firestore_collection,
            local_storage_path=local_storage_path,
            use_local_llm=use_local_llm,
            local_model=local_model,
        )
    
    def summary(self) -> dict:
        """
        Get configuration summary.
        
        Returns:
            dict: Configuration summary
        """
        return {
            "environment": self.environment,
            "is_cloud": self.is_cloud,
            "storage": {
                "profile": "firestore" if self.use_firestore else "json",
                "rag": "vertex_ai" if self.use_vertex_rag else "chromadb",
            },
            "llm": {
                "backend": "gemini" if not self.use_local_llm else "local",
                "model": self.local_model if self.use_local_llm else "gemini-1.5-flash",
            },
            "gcp": {
                "project": self.project_id,
                "location": self.location,
            } if self.is_cloud else None,
        }


def get_config() -> AppConfig:
    """
    Get application configuration.
    
    Convenience function for accessing config.
    
    Returns:
        AppConfig: Configuration instance
    """
    return AppConfig.from_env()


def should_use_vertex_rag() -> bool:
    """
    Check if Vertex AI RAG should be used.
    
    Returns:
        bool: True if Vertex AI RAG should be used
    """
    config = get_config()
    return config.use_vertex_rag
