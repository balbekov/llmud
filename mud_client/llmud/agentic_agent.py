"""
Agentic AI Agent - Tool-based agent for MUD gameplay.

This agent uses tool calls to interact with the MUD, maintaining:
1. A high-level goal
2. Observations about current state
3. A todo list for tactical planning
4. A knowledge base for learned rules

All MUD interactions are done via tool calls, enabling structured reasoning.
"""

import os
import json
import logging
import asyncio
from typing import Optional, Any, Literal, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ==================== Tool Definitions ====================

AGENT_TOOLS = [
    # MUD Interaction Tools
    {
        "name": "send_command",
        "description": "Send a command to the MUD. Use this for any action like moving, fighting, looking, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The MUD command to send (e.g., 'n', 'kill orc', 'look', 'score')"
                },
                "wait_for_response": {
                    "type": "boolean",
                    "description": "Whether to wait for and return the MUD's response (default true)"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "look",
        "description": "Look at the current room or a specific target. Returns the description.",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Optional target to look at (e.g., 'guard', 'door', 'sword')"
                }
            }
        }
    },
    {
        "name": "move",
        "description": "Move in a direction. Returns success/failure and new room info.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "description": "Direction to move: n, s, e, w, ne, nw, se, sw, u, d, enter, out"
                }
            },
            "required": ["direction"]
        }
    },
    {
        "name": "check_status",
        "description": "Check character status including HP, CP, money, location, etc.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    
    # Goal & Planning Tools
    {
        "name": "set_goal",
        "description": "Set or update the current high-level goal.",
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "The high-level goal to achieve (e.g., 'Explore the Astroport area', 'Find a shop to sell items')"
                },
                "priority": {
                    "type": "string",
                    "description": "Priority level: low, medium, high, critical",
                    "enum": ["low", "medium", "high", "critical"]
                }
            },
            "required": ["goal"]
        }
    },
    {
        "name": "update_observation",
        "description": "Update observation about the current situation or state.",
        "parameters": {
            "type": "object",
            "properties": {
                "observation": {
                    "type": "string",
                    "description": "Current observation about the room, NPCs, situation, etc."
                },
                "category": {
                    "type": "string",
                    "description": "Category of observation",
                    "enum": ["room", "combat", "npc", "item", "navigation", "danger", "opportunity"]
                }
            },
            "required": ["observation"]
        }
    },
    {
        "name": "add_todo",
        "description": "Add a task to the todo list.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task to add"
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority (1-5, higher is more important)"
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "complete_todo",
        "description": "Mark a todo item as complete.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "The ID of the task to complete"
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "clear_todos",
        "description": "Clear all completed todos or all todos.",
        "parameters": {
            "type": "object",
            "properties": {
                "completed_only": {
                    "type": "boolean",
                    "description": "If true, only clear completed todos. If false, clear all."
                }
            }
        }
    },
    
    # Knowledge Tools
    {
        "name": "update_knowledge",
        "description": "Add or update knowledge in the persistent knowledge base. Use this when learning new rules, facts, or strategies about the MUD.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category of knowledge",
                    "enum": ["combat", "navigation", "economy", "guilds", "quests", "npcs", "items", "rules", "strategies"]
                },
                "key": {
                    "type": "string",
                    "description": "Unique key for this piece of knowledge"
                },
                "content": {
                    "type": "string",
                    "description": "The knowledge content"
                },
                "importance": {
                    "type": "string",
                    "description": "How important this knowledge is",
                    "enum": ["low", "medium", "high", "critical"]
                }
            },
            "required": ["category", "key", "content"]
        }
    },
    {
        "name": "query_knowledge",
        "description": "Query the knowledge base for relevant information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for the knowledge base"
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter"
                }
            },
            "required": ["query"]
        }
    },
    
    # Map Tools
    {
        "name": "query_map",
        "description": "Query the world map for information about rooms, areas, or paths.",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "Type of query",
                    "enum": ["current_room", "adjacent_rooms", "area_rooms", "find_room", "unexplored"]
                },
                "search_term": {
                    "type": "string",
                    "description": "Search term for find_room or area_rooms queries"
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum depth for searches (default 10)"
                }
            },
            "required": ["query_type"]
        }
    },
    {
        "name": "get_route",
        "description": "Get a route from current location to a destination.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "Destination room ID, room name, or tag (e.g., 'shop', 'inn', 'bank')"
                },
                "max_steps": {
                    "type": "integer",
                    "description": "Maximum number of steps in the route (default 50)"
                }
            },
            "required": ["destination"]
        }
    },
    {
        "name": "find_nearby",
        "description": "Find nearby rooms with specific features.",
        "parameters": {
            "type": "object",
            "properties": {
                "feature": {
                    "type": "string",
                    "description": "Feature to search for (e.g., 'shop', 'npc', 'unexplored', 'dangerous')"
                },
                "max_distance": {
                    "type": "integer",
                    "description": "Maximum distance to search (default 5)"
                }
            },
            "required": ["feature"]
        }
    },
    
    # Control Tools
    {
        "name": "wait",
        "description": "Wait for a specified time or event.",
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "Seconds to wait (default 1)"
                },
                "for_event": {
                    "type": "string",
                    "description": "Optional event type to wait for: combat_end, hp_restore, room_change"
                }
            }
        }
    },
    {
        "name": "report_complete",
        "description": "Report that the current goal has been completed.",
        "parameters": {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "description": "Whether the goal was successfully achieved"
                },
                "summary": {
                    "type": "string",
                    "description": "Summary of what was accomplished"
                }
            },
            "required": ["success", "summary"]
        }
    }
]


@dataclass
class TodoItem:
    """A todo item for tactical planning."""
    id: int
    task: str
    priority: int = 3
    completed: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task": self.task,
            "priority": self.priority,
            "completed": self.completed,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Observation:
    """An observation about the current state."""
    text: str
    category: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "category": self.category,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AgentState:
    """Current state of the agent."""
    goal: str = ""
    goal_priority: str = "medium"
    observations: list[Observation] = field(default_factory=list)
    todos: list[TodoItem] = field(default_factory=list)
    next_todo_id: int = 1
    total_commands_sent: int = 0
    total_tokens_used: int = 0
    session_start: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "goal_priority": self.goal_priority,
            "observations": [o.to_dict() for o in self.observations[-10:]],  # Last 10
            "todos": [t.to_dict() for t in self.todos if not t.completed],
            "total_commands_sent": self.total_commands_sent,
            "total_tokens_used": self.total_tokens_used,
            "session_duration": str(datetime.now() - self.session_start)
        }


class KnowledgeBase:
    """Persistent knowledge base for learned rules and facts."""
    
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else Path("knowledge_base.json")
        self.knowledge: dict[str, dict[str, dict]] = {}
        self.load()
    
    def load(self) -> None:
        """Load knowledge from disk."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    self.knowledge = json.load(f)
                logger.info(f"Loaded knowledge base from {self.path}")
            except Exception as e:
                logger.warning(f"Could not load knowledge base: {e}")
                self.knowledge = {}
        else:
            self.knowledge = {}
    
    def save(self) -> None:
        """Save knowledge to disk."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.knowledge, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save knowledge base: {e}")
    
    def update(self, category: str, key: str, content: str, importance: str = "medium") -> None:
        """Add or update knowledge."""
        if category not in self.knowledge:
            self.knowledge[category] = {}
        
        self.knowledge[category][key] = {
            "content": content,
            "importance": importance,
            "updated_at": datetime.now().isoformat()
        }
        self.save()
    
    def query(self, query: str, category: Optional[str] = None) -> list[dict]:
        """Search knowledge base."""
        results = []
        query_lower = query.lower()
        
        categories_to_search = [category] if category else self.knowledge.keys()
        
        for cat in categories_to_search:
            if cat not in self.knowledge:
                continue
            
            for key, data in self.knowledge[cat].items():
                if query_lower in key.lower() or query_lower in data["content"].lower():
                    results.append({
                        "category": cat,
                        "key": key,
                        "content": data["content"],
                        "importance": data["importance"]
                    })
        
        # Sort by importance
        importance_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        results.sort(key=lambda x: importance_order.get(x["importance"], 2))
        
        return results[:10]  # Limit to 10 results
    
    def get_summary(self) -> str:
        """Get a summary of all knowledge."""
        lines = []
        for category, items in self.knowledge.items():
            lines.append(f"\n## {category.title()}")
            for key, data in items.items():
                if data["importance"] in ("critical", "high"):
                    lines.append(f"- **{key}**: {data['content']}")
        return "\n".join(lines) if lines else "No knowledge recorded yet."


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    result: Any
    message: str = ""


class AgenticAgent:
    """
    Tool-based AI agent for MUD gameplay.
    
    Uses structured tool calls for all interactions, maintaining
    goals, observations, and a todo list for planning.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        knowledge_path: Optional[str] = None,
        send_command_callback: Optional[Callable] = None,
        get_state_callback: Optional[Callable] = None,
        get_output_callback: Optional[Callable] = None,
        map_agent: Optional[Any] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = None
        
        # Callbacks for MUD interaction
        self._send_command = send_command_callback
        self._get_state = get_state_callback
        self._get_output = get_output_callback
        self._map_agent = map_agent
        
        # Agent state
        self.state = AgentState()
        
        # Knowledge base
        self.knowledge = KnowledgeBase(knowledge_path)
        
        # Response buffer for collecting MUD output
        self._response_buffer: list[str] = []
        self._waiting_for_response = False
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 0.5
        
        # Conversation history for context
        self._conversation: list[dict] = []
        self._max_conversation_turns = 20
        
        # Goal completion flag
        self._goal_complete = False
        self._goal_result: Optional[dict] = None
    
    def _get_client(self):
        """Lazy load the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client
    
    def set_callbacks(
        self,
        send_command: Optional[Callable] = None,
        get_state: Optional[Callable] = None,
        get_output: Optional[Callable] = None,
        map_agent: Optional[Any] = None,
    ) -> None:
        """Set callbacks for MUD interaction."""
        if send_command:
            self._send_command = send_command
        if get_state:
            self._get_state = get_state
        if get_output:
            self._get_output = get_output
        if map_agent:
            self._map_agent = map_agent
    
    def add_mud_output(self, text: str) -> None:
        """Add MUD output to the response buffer."""
        if text.strip():
            self._response_buffer.append(text)
    
    def get_and_clear_output(self) -> str:
        """Get accumulated output and clear buffer."""
        output = "\n".join(self._response_buffer)
        self._response_buffer.clear()
        return output
    
    # ==================== Tool Execution ====================
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> ToolResult:
        """Execute a tool and return the result."""
        try:
            if tool_name == "send_command":
                return await self._tool_send_command(**arguments)
            elif tool_name == "look":
                return await self._tool_look(**arguments)
            elif tool_name == "move":
                return await self._tool_move(**arguments)
            elif tool_name == "check_status":
                return await self._tool_check_status()
            elif tool_name == "set_goal":
                return self._tool_set_goal(**arguments)
            elif tool_name == "update_observation":
                return self._tool_update_observation(**arguments)
            elif tool_name == "add_todo":
                return self._tool_add_todo(**arguments)
            elif tool_name == "complete_todo":
                return self._tool_complete_todo(**arguments)
            elif tool_name == "clear_todos":
                return self._tool_clear_todos(**arguments)
            elif tool_name == "update_knowledge":
                return self._tool_update_knowledge(**arguments)
            elif tool_name == "query_knowledge":
                return self._tool_query_knowledge(**arguments)
            elif tool_name == "query_map":
                return self._tool_query_map(**arguments)
            elif tool_name == "get_route":
                return self._tool_get_route(**arguments)
            elif tool_name == "find_nearby":
                return self._tool_find_nearby(**arguments)
            elif tool_name == "wait":
                return await self._tool_wait(**arguments)
            elif tool_name == "report_complete":
                return self._tool_report_complete(**arguments)
            else:
                return ToolResult(False, None, f"Unknown tool: {tool_name}")
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return ToolResult(False, None, f"Error: {str(e)}")
    
    # Commands that should be blocked for safety
    BLOCKED_COMMANDS = {"quit", "suicide", "delete", "drop all", "give all"}
    
    async def _tool_send_command(
        self, 
        command: str, 
        wait_for_response: bool = True
    ) -> ToolResult:
        """Send a command to the MUD."""
        if not self._send_command:
            return ToolResult(False, None, "No send_command callback configured")
        
        # Safety check - block dangerous commands
        cmd_lower = command.lower().strip()
        if cmd_lower in self.BLOCKED_COMMANDS or cmd_lower.startswith("quit"):
            return ToolResult(False, None, f"Blocked dangerous command: {command}")
        
        self.state.total_commands_sent += 1
        
        # Clear output buffer before sending
        self._response_buffer.clear()
        
        # Send the command
        await self._send_command(command)
        
        response = ""
        if wait_for_response:
            # Wait for response - multiple checks to catch async output
            for _ in range(10):  # Wait up to 2 seconds
                await asyncio.sleep(0.2)
                response = self.get_and_clear_output()
                if response.strip():
                    break
        
        return ToolResult(
            True,
            {"command": command, "response": response},
            f"Sent: {command}" + (f" - Response: {response[:100]}" if response else "")
        )
    
    async def _tool_look(self, target: Optional[str] = None) -> ToolResult:
        """Look at the room or a target."""
        command = f"look {target}" if target else "look"
        return await self._tool_send_command(command, wait_for_response=True)
    
    async def _tool_move(self, direction: str) -> ToolResult:
        """Move in a direction."""
        return await self._tool_send_command(direction, wait_for_response=True)
    
    async def _tool_check_status(self) -> ToolResult:
        """Get character status."""
        if self._get_state:
            state = self._get_state()
            return ToolResult(True, state, "Got current status")
        return ToolResult(False, None, "No get_state callback configured")
    
    def _tool_set_goal(self, goal: str, priority: str = "medium") -> ToolResult:
        """Set the current goal."""
        self.state.goal = goal
        self.state.goal_priority = priority
        self._goal_complete = False
        return ToolResult(True, {"goal": goal, "priority": priority}, f"Goal set: {goal}")
    
    def _tool_update_observation(
        self, 
        observation: str, 
        category: str = "room"
    ) -> ToolResult:
        """Update current observation."""
        obs = Observation(text=observation, category=category)
        self.state.observations.append(obs)
        # Keep only last 20 observations
        self.state.observations = self.state.observations[-20:]
        return ToolResult(True, obs.to_dict(), "Observation recorded")
    
    def _tool_add_todo(self, task: str, priority: int = 3) -> ToolResult:
        """Add a todo item."""
        todo = TodoItem(
            id=self.state.next_todo_id,
            task=task,
            priority=priority
        )
        self.state.todos.append(todo)
        self.state.next_todo_id += 1
        return ToolResult(True, todo.to_dict(), f"Added todo #{todo.id}: {task}")
    
    def _tool_complete_todo(self, task_id: int) -> ToolResult:
        """Mark a todo as complete."""
        for todo in self.state.todos:
            if todo.id == task_id:
                todo.completed = True
                return ToolResult(True, todo.to_dict(), f"Completed todo #{task_id}")
        return ToolResult(False, None, f"Todo #{task_id} not found")
    
    def _tool_clear_todos(self, completed_only: bool = True) -> ToolResult:
        """Clear todos."""
        if completed_only:
            self.state.todos = [t for t in self.state.todos if not t.completed]
            return ToolResult(True, None, "Cleared completed todos")
        else:
            self.state.todos.clear()
            return ToolResult(True, None, "Cleared all todos")
    
    def _tool_update_knowledge(
        self, 
        category: str, 
        key: str, 
        content: str,
        importance: str = "medium"
    ) -> ToolResult:
        """Update knowledge base."""
        self.knowledge.update(category, key, content, importance)
        return ToolResult(
            True, 
            {"category": category, "key": key},
            f"Knowledge updated: {category}/{key}"
        )
    
    def _tool_query_knowledge(
        self, 
        query: str, 
        category: Optional[str] = None
    ) -> ToolResult:
        """Query knowledge base."""
        results = self.knowledge.query(query, category)
        return ToolResult(True, results, f"Found {len(results)} results")
    
    def _tool_query_map(
        self, 
        query_type: str,
        search_term: Optional[str] = None,
        max_depth: int = 10
    ) -> ToolResult:
        """Query the map."""
        if not self._map_agent:
            return ToolResult(False, None, "No map agent configured")
        
        try:
            if query_type == "current_room":
                info = self._map_agent.get_current_room_info()
                return ToolResult(True, info, "Got current room info")
            
            elif query_type == "adjacent_rooms":
                info = self._map_agent.get_adjacent_rooms_info()
                return ToolResult(True, info, f"Found {len(info)} adjacent rooms")
            
            elif query_type == "area_rooms":
                if not search_term:
                    return ToolResult(False, None, "search_term required for area_rooms")
                rooms = self._map_agent.map.find_rooms_by_area(search_term)
                # Limit results
                rooms_data = [
                    {"room_id": r.room_id, "name": r.name, "exits": list(r.exits.keys())}
                    for r in rooms[:max_depth]
                ]
                return ToolResult(True, rooms_data, f"Found {len(rooms_data)} rooms in {search_term}")
            
            elif query_type == "find_room":
                if not search_term:
                    return ToolResult(False, None, "search_term required for find_room")
                rooms = self._map_agent.map.find_rooms_by_name(search_term)
                rooms_data = [
                    {"room_id": r.room_id, "name": r.name, "area": r.area}
                    for r in rooms[:max_depth]
                ]
                return ToolResult(True, rooms_data, f"Found {len(rooms_data)} matching rooms")
            
            elif query_type == "unexplored":
                unexplored = self._map_agent.map.get_unexplored_exits()
                unexplored_data = unexplored[:max_depth]
                return ToolResult(True, unexplored_data, f"Found {len(unexplored_data)} unexplored exits")
            
            else:
                return ToolResult(False, None, f"Unknown query_type: {query_type}")
        
        except Exception as e:
            return ToolResult(False, None, f"Map query error: {e}")
    
    def _tool_get_route(
        self, 
        destination: str,
        max_steps: int = 50
    ) -> ToolResult:
        """Get a route to destination."""
        if not self._map_agent:
            return ToolResult(False, None, "No map agent configured")
        
        try:
            route_info = self._map_agent.get_route_to(destination)
            if route_info:
                # Limit route length
                if route_info.get("directions"):
                    route_info["directions"] = route_info["directions"][:max_steps]
                return ToolResult(True, route_info, f"Route found: {route_info.get('route', '')}")
            return ToolResult(False, None, f"No route found to {destination}")
        except Exception as e:
            return ToolResult(False, None, f"Route error: {e}")
    
    def _tool_find_nearby(
        self, 
        feature: str,
        max_distance: int = 5
    ) -> ToolResult:
        """Find nearby rooms with features."""
        if not self._map_agent:
            return ToolResult(False, None, "No map agent configured")
        
        try:
            # Handle different feature types
            if feature in ("shop", "inn", "bank", "guild", "dangerous", "quest"):
                result = self._map_agent._tool_find_nearest_tagged(feature)
                if result.success:
                    # Check distance
                    if result.data and result.data.get("steps", 0) <= max_distance:
                        return ToolResult(True, result.data, result.message)
                    return ToolResult(False, None, f"No {feature} within {max_distance} steps")
                return result
            
            elif feature == "unexplored":
                unexplored = self._map_agent.map.get_unexplored_exits()
                nearby = unexplored[:max_distance]
                return ToolResult(True, nearby, f"Found {len(nearby)} nearby unexplored exits")
            
            else:
                # Try as a tag
                result = self._map_agent._tool_find_nearest_tagged(feature)
                return result
        
        except Exception as e:
            return ToolResult(False, None, f"Search error: {e}")
    
    async def _tool_wait(
        self, 
        seconds: float = 1.0,
        for_event: Optional[str] = None
    ) -> ToolResult:
        """Wait for time or event."""
        await asyncio.sleep(seconds)
        output = self.get_and_clear_output()
        return ToolResult(True, {"waited": seconds, "output": output}, f"Waited {seconds}s")
    
    def _tool_report_complete(self, success: bool, summary: str) -> ToolResult:
        """Report goal completion."""
        self._goal_complete = True
        self._goal_result = {"success": success, "summary": summary}
        return ToolResult(True, self._goal_result, f"Goal {'completed' if success else 'failed'}: {summary}")
    
    # ==================== Agent Loop ====================
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent."""
        knowledge_summary = self.knowledge.get_summary()
        
        return f"""You are an AI agent playing DuneMUD, a text-based multiplayer game set in the Dune universe.

## Your Capabilities
You interact with the MUD ONLY through tool calls. Each action you take should be a tool call.

## Current State
- Goal: {self.state.goal or 'No goal set'}
- Priority: {self.state.goal_priority}
- Commands sent: {self.state.total_commands_sent}

## Todo List
{self._format_todos()}

## Recent Observations
{self._format_observations()}

## Knowledge Base
{knowledge_summary}

## Guidelines
1. ALWAYS use tool calls for actions - never output raw MUD commands
2. Think step by step before acting
3. Use check_status to understand your current situation
4. Use update_observation to record important findings
5. Use add_todo to break down complex goals
6. Use update_knowledge when you learn important rules
7. When the goal is achieved, use report_complete

## Safety Rules
- If HP is low (below 30%), prioritize fleeing and healing
- Don't attack NPCs much stronger than you
- Keep some money for emergencies
- Explore carefully in new areas
"""
    
    def _format_todos(self) -> str:
        """Format todos for the prompt."""
        pending = [t for t in self.state.todos if not t.completed]
        if not pending:
            return "No pending tasks"
        
        lines = []
        for t in sorted(pending, key=lambda x: -x.priority):
            lines.append(f"- [{t.id}] (P{t.priority}) {t.task}")
        return "\n".join(lines)
    
    def _format_observations(self) -> str:
        """Format recent observations for the prompt."""
        recent = self.state.observations[-5:]
        if not recent:
            return "No observations yet"
        
        lines = []
        for o in recent:
            lines.append(f"- [{o.category}] {o.text}")
        return "\n".join(lines)
    
    def _build_user_prompt(self, game_state: dict, recent_output: str) -> str:
        """Build the user prompt with current context."""
        character = game_state.get("character", {})
        room = game_state.get("room", {})
        
        prompt = f"""## Current Game State

### Character
- Name: {character.get('name', 'Unknown')}
- HP: {character.get('hp', '?')} ({character.get('hp_percent', 0):.0f}%)
- CP: {character.get('cp', '?')} ({character.get('cp_percent', 0):.0f}%)
- Money: {character.get('money', 0)}
- Wimpy: {character.get('wimpy', 0)}%

### Location
- Room: {room.get('name', 'Unknown')}
- Area: {room.get('area', 'Unknown')}
- Exits: {', '.join(room.get('exits', [])) or 'none'}

### Recent MUD Output
```
{recent_output[-2000:] if recent_output else 'No recent output'}
```

What is your next action? Use tool calls to interact with the game."""
        
        return prompt
    
    async def think_and_act(
        self, 
        game_state: Optional[dict] = None,
        recent_output: Optional[str] = None,
        max_tool_calls: int = 10
    ) -> list[ToolResult]:
        """
        Main agent loop: think about the situation and take action.
        Returns list of tool results from this thinking cycle.
        """
        import time
        
        # Rate limiting
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        
        # Get state if not provided
        if game_state is None and self._get_state:
            game_state = self._get_state()
        game_state = game_state or {}
        
        # Get output if not provided
        if recent_output is None:
            recent_output = self.get_and_clear_output()
        
        # Build prompts
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(game_state, recent_output)
        
        # Add to conversation
        self._conversation.append({"role": "user", "content": user_prompt})
        
        # Trim conversation history
        if len(self._conversation) > self._max_conversation_turns * 2:
            self._conversation = self._conversation[-self._max_conversation_turns * 2:]
        
        results = []
        tool_calls_made = 0
        
        try:
            client = self._get_client()
            
            # Convert tools to OpenAI format
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["parameters"],
                    }
                }
                for tool in AGENT_TOOLS
            ]
            
            # Initial request
            messages = [
                {"role": "system", "content": system_prompt},
                *self._conversation
            ]
            
            while tool_calls_made < max_tool_calls:
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.3,
                )
                
                self._last_request_time = time.time()
                
                message = response.choices[0].message
                self.state.total_tokens_used += response.usage.total_tokens if response.usage else 0
                
                # Add assistant message to conversation (only for non-tool responses)
                if not message.tool_calls:
                    self._conversation.append({
                        "role": "assistant",
                        "content": message.content or "",
                    })
                
                # Check if we have tool calls
                if not message.tool_calls:
                    break
                
                # Add assistant message with tool calls to messages (once, before processing)
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                })
                
                # Execute tool calls and add results
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    logger.info(f"Executing tool: {tool_name}({arguments})")
                    result = await self.execute_tool(tool_name, arguments)
                    results.append(result)
                    tool_calls_made += 1
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                            "success": result.success,
                            "result": result.result,
                            "message": result.message
                        })
                    })
                    
                    # Check if goal is complete
                    if self._goal_complete:
                        logger.info(f"Goal complete: {self._goal_result}")
                        return results
                
                # Check stop condition
                if response.choices[0].finish_reason == "stop":
                    break
        
        except Exception as e:
            logger.error(f"Agent think_and_act error: {e}")
            results.append(ToolResult(False, None, f"Agent error: {e}"))
            # Clear conversation on errors to prevent cascading failures
            self._conversation.clear()
        
        return results
    
    def is_goal_complete(self) -> bool:
        """Check if the current goal is complete."""
        return self._goal_complete
    
    def get_goal_result(self) -> Optional[dict]:
        """Get the result of the completed goal."""
        return self._goal_result
    
    def reset_goal(self) -> None:
        """Reset goal completion state."""
        self._goal_complete = False
        self._goal_result = None
        self.state.goal = ""
    
    def get_state_summary(self) -> dict:
        """Get a summary of the agent's current state."""
        return self.state.to_dict()
