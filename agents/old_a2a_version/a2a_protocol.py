"""
A2A (Agent-to-Agent) Protocol base classes.

This module provides base classes for agent communication following the
Agent-to-Agent protocol for future extensibility and interoperability.

Currently implemented as a foundation without active A2A communication,
but agents are structured to be A2A-compliant for future integration.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class MessageType(Enum):
    """Types of messages in A2A protocol."""
    
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    INFO = "info"


@dataclass
class A2AMessage:
    """
    Agent-to-Agent message format.
    
    Follows A2A protocol structure for future-proof agent communication.
    """
    
    sender: str
    recipient: str
    message_type: MessageType
    content: Any
    correlation_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert message to dictionary format."""
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "message_type": self.message_type.value,
            "content": self.content,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }


@dataclass
class AgentCapability:
    """
    Describes what an agent can do.
    
    Used for agent discovery and routing in A2A protocol.
    """
    
    name: str
    description: str
    input_schema: dict
    output_schema: dict


class A2AAgent(ABC):
    """
    Base class for A2A-compliant agents.
    
    All agents inherit from this to ensure compatibility with
    future A2A protocol implementations.
    """
    
    def __init__(self, agent_id: str, name: str):
        """
        Initialize A2A agent.
        
        Args:
            agent_id: Unique identifier for this agent
            name: Human-readable name
        """
        self.agent_id = agent_id
        self.name = name
        self._capabilities: list[AgentCapability] = []
    
    @abstractmethod
    def process(self, message: A2AMessage) -> A2AMessage:
        """
        Process an A2A message and return a response.
        
        Args:
            message: Input message to process
            
        Returns:
            Response message
        """
        pass
    
    def get_capabilities(self) -> list[AgentCapability]:
        """
        Get list of agent capabilities.
        
        Returns:
            List of capabilities this agent supports
        """
        return self._capabilities
    
    def register_capability(self, capability: AgentCapability):
        """
        Register a new capability for this agent.
        
        Args:
            capability: Capability to register
        """
        self._capabilities.append(capability)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.agent_id}, name={self.name})"
