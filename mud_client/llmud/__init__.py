"""
LLMUD - AI-Powered MUD Client

A Python package for connecting to MUDs with LLM-driven gameplay.
"""

__version__ = "0.1.0"

from .telnet_client import TelnetClient
from .gmcp_handler import GMCPHandler
from .game_state import GameState, GamePhase
from .context_manager import ContextManager
from .llm_agent import LLMAgent
from .mud_session import MUDSession, SessionConfig
from .map_graph import (
    MapGraph,
    RoomNode,
    RoomItem,
    RoomNPC,
    MapEdge,
    Direction,
)
from .map_agent import MapAgent, MappingContext, MapUpdateResult

__all__ = [
    # Core components
    "TelnetClient",
    "GMCPHandler", 
    "GameState",
    "GamePhase",
    "ContextManager",
    "LLMAgent",
    "MUDSession",
    "SessionConfig",
    # Mapping components
    "MapGraph",
    "RoomNode",
    "RoomItem",
    "RoomNPC",
    "MapEdge",
    "Direction",
    "MapAgent",
    "MappingContext",
    "MapUpdateResult",
]
