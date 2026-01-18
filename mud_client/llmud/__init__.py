"""
LLMUD - AI-Powered MUD Client

A Python package for connecting to MUDs with LLM-driven gameplay.
"""

__version__ = "0.2.0"

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
from .terminal_app import TerminalApp, AppConfig

# New agentic architecture
from .agentic_agent import AgenticAgent, KnowledgeBase, AgentState, ToolResult
from .agentic_session import AgenticSession, AgenticSessionConfig, create_session, quick_test
from .eval_framework import EvalRunner, EvalSuite, EvalResult, EvalReport

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
    # Terminal app
    "TerminalApp",
    "AppConfig",
    # Agentic AI components
    "AgenticAgent",
    "AgentState",
    "KnowledgeBase",
    "ToolResult",
    "AgenticSession",
    "AgenticSessionConfig",
    "create_session",
    "quick_test",
    # Evaluation framework
    "EvalRunner",
    "EvalSuite",
    "EvalResult",
    "EvalReport",
]
