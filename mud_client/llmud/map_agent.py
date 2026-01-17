"""
Map Agent - LLM-based mapping agent that uses tool calls to update the world map.

The agent:
1. Receives room data from GMCP and text output
2. Uses LLM to analyze and extract map information
3. Mutates the map graph via tool calls
4. Tracks the current room and supports routing
"""

import os
import json
import logging
import asyncio
from typing import Optional, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .map_graph import MapGraph, RoomNode, RoomItem, RoomNPC, MapEdge

logger = logging.getLogger(__name__)


# ==================== Tool Definitions ====================

MAP_TOOLS = [
    {
        "name": "add_room",
        "description": "Add a new room to the map or update an existing room. Use this when entering a new room or when room details have been observed.",
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Unique identifier for the room (usually from GMCP)"
                },
                "name": {
                    "type": "string",
                    "description": "The name/title of the room"
                },
                "area": {
                    "type": "string",
                    "description": "The area/region the room belongs to"
                },
                "environment": {
                    "type": "string",
                    "description": "The environment type (e.g., 'indoor', 'outdoor', 'desert', 'city')"
                },
                "description": {
                    "type": "string",
                    "description": "Full description of the room"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for the room (e.g., 'shop', 'inn', 'dangerous', 'quest')"
                }
            },
            "required": ["room_id", "name"]
        }
    },
    {
        "name": "add_exit",
        "description": "Add an exit/connection from one room to another. Use this when discovering a new path.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_room_id": {
                    "type": "string",
                    "description": "Room ID where the exit starts"
                },
                "to_room_id": {
                    "type": "string",
                    "description": "Room ID where the exit leads"
                },
                "direction": {
                    "type": "string",
                    "description": "Direction of the exit (n, s, e, w, ne, nw, se, sw, u, d, enter, out)"
                },
                "bidirectional": {
                    "type": "boolean",
                    "description": "Whether the connection works both ways (default true)"
                }
            },
            "required": ["from_room_id", "to_room_id", "direction"]
        }
    },
    {
        "name": "add_item",
        "description": "Add or update an item in a room. Use this when items are observed in a room.",
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Room ID where the item is located"
                },
                "name": {
                    "type": "string",
                    "description": "Name of the item"
                },
                "description": {
                    "type": "string",
                    "description": "Description of the item"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of items (default 1)"
                }
            },
            "required": ["room_id", "name"]
        }
    },
    {
        "name": "remove_item",
        "description": "Remove an item from a room. Use when an item is no longer present.",
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Room ID where the item was located"
                },
                "name": {
                    "type": "string",
                    "description": "Name of the item to remove"
                }
            },
            "required": ["room_id", "name"]
        }
    },
    {
        "name": "add_npc",
        "description": "Add or update an NPC in a room. Use when NPCs are observed.",
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Room ID where the NPC is located"
                },
                "name": {
                    "type": "string",
                    "description": "Name of the NPC"
                },
                "description": {
                    "type": "string",
                    "description": "Description of the NPC"
                },
                "level": {
                    "type": "string",
                    "description": "Difficulty level (easy, medium, hard, deadly)"
                },
                "hostile": {
                    "type": "boolean",
                    "description": "Whether the NPC is hostile"
                }
            },
            "required": ["room_id", "name"]
        }
    },
    {
        "name": "remove_npc",
        "description": "Remove an NPC from a room. Use when an NPC is no longer present.",
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Room ID where the NPC was located"
                },
                "name": {
                    "type": "string",
                    "description": "Name of the NPC to remove"
                }
            },
            "required": ["room_id", "name"]
        }
    },
    {
        "name": "set_current_room",
        "description": "Set the player's current room location.",
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Room ID of the current location"
                }
            },
            "required": ["room_id"]
        }
    },
    {
        "name": "add_room_tag",
        "description": "Add a tag to a room for categorization.",
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Room ID to tag"
                },
                "tag": {
                    "type": "string",
                    "description": "Tag to add (e.g., 'shop', 'inn', 'dangerous', 'quest_giver')"
                }
            },
            "required": ["room_id", "tag"]
        }
    },
    {
        "name": "add_room_note",
        "description": "Add a note to a room for future reference.",
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Room ID to annotate"
                },
                "note": {
                    "type": "string",
                    "description": "Note text to add"
                }
            },
            "required": ["room_id", "note"]
        }
    },
    {
        "name": "set_room_image",
        "description": "Set the image path and prompt for a room visualization.",
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Room ID to set image for"
                },
                "image_path": {
                    "type": "string",
                    "description": "Path to the saved image file"
                },
                "image_prompt": {
                    "type": "string",
                    "description": "The prompt used to generate the image"
                }
            },
            "required": ["room_id"]
        }
    },
    {
        "name": "find_route",
        "description": "Find a route from current room to a destination.",
        "parameters": {
            "type": "object",
            "properties": {
                "to_room_id": {
                    "type": "string",
                    "description": "Destination room ID"
                },
                "from_room_id": {
                    "type": "string",
                    "description": "Starting room ID (defaults to current room)"
                }
            },
            "required": ["to_room_id"]
        }
    },
    {
        "name": "find_nearest_tagged",
        "description": "Find the nearest room with a specific tag.",
        "parameters": {
            "type": "object",
            "properties": {
                "tag": {
                    "type": "string",
                    "description": "Tag to search for (e.g., 'shop', 'inn', 'bank')"
                }
            },
            "required": ["tag"]
        }
    }
]


@dataclass
class MapUpdateResult:
    """Result of a map update operation."""
    success: bool
    tool_name: str
    message: str
    data: Optional[dict] = None


@dataclass
class MappingContext:
    """Context for the mapping agent."""
    current_room_id: Optional[str] = None
    current_room_name: str = ""
    current_area: str = ""
    current_environment: str = ""
    current_exits: list[str] = field(default_factory=list)
    room_description: str = ""
    recent_movement: Optional[str] = None  # Last direction moved
    previous_room_id: Optional[str] = None


class MapAgent:
    """
    LLM-based mapping agent that uses tool calls to maintain the world map.
    
    Features:
    - Automatic room tracking from GMCP data
    - LLM-powered analysis of room descriptions
    - Tool-based map mutations
    - Route finding and navigation
    - Persistent map storage
    """
    
    def __init__(
        self,
        provider: Literal["openai", "anthropic"] = "anthropic",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        map_path: Optional[str] = None,
        auto_save: bool = True,
        images_dir: Optional[str] = None,
    ):
        self.provider_name = provider
        self.api_key = api_key or os.getenv(
            "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
        )
        self.model = model
        self.auto_save = auto_save
        self.images_dir = Path(images_dir) if images_dir else Path("./map_images")
        
        # Map state
        self.map = MapGraph(name="world")
        self.map_path = Path(map_path) if map_path else None
        
        # Load existing map if path provided
        if self.map_path and self.map_path.exists():
            try:
                self.map = MapGraph.load_json(self.map_path)
                logger.info(f"Loaded existing map with {len(self.map.rooms)} rooms")
            except Exception as e:
                logger.warning(f"Could not load map from {self.map_path}: {e}")
        
        # Context tracking
        self.context = MappingContext()
        
        # LLM client (lazy loaded)
        self._client = None
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 0.5
        
        # Update queue for batching
        self._pending_updates: list[dict] = []

    def _get_client(self):
        """Lazy load the LLM client."""
        if self._client is not None:
            return self._client
        
        if self.provider_name == "openai":
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        else:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
        
        return self._client

    # ==================== Tool Execution ====================
    
    def execute_tool(self, tool_name: str, arguments: dict) -> MapUpdateResult:
        """Execute a map mutation tool."""
        try:
            if tool_name == "add_room":
                return self._tool_add_room(**arguments)
            elif tool_name == "add_exit":
                return self._tool_add_exit(**arguments)
            elif tool_name == "add_item":
                return self._tool_add_item(**arguments)
            elif tool_name == "remove_item":
                return self._tool_remove_item(**arguments)
            elif tool_name == "add_npc":
                return self._tool_add_npc(**arguments)
            elif tool_name == "remove_npc":
                return self._tool_remove_npc(**arguments)
            elif tool_name == "set_current_room":
                return self._tool_set_current_room(**arguments)
            elif tool_name == "add_room_tag":
                return self._tool_add_room_tag(**arguments)
            elif tool_name == "add_room_note":
                return self._tool_add_room_note(**arguments)
            elif tool_name == "set_room_image":
                return self._tool_set_room_image(**arguments)
            elif tool_name == "find_route":
                return self._tool_find_route(**arguments)
            elif tool_name == "find_nearest_tagged":
                return self._tool_find_nearest_tagged(**arguments)
            else:
                return MapUpdateResult(
                    success=False,
                    tool_name=tool_name,
                    message=f"Unknown tool: {tool_name}"
                )
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return MapUpdateResult(
                success=False,
                tool_name=tool_name,
                message=f"Error: {str(e)}"
            )
    
    def _tool_add_room(
        self,
        room_id: str,
        name: str,
        area: str = "",
        environment: str = "",
        description: str = "",
        tags: Optional[list[str]] = None,
    ) -> MapUpdateResult:
        """Add or update a room."""
        is_new = room_id not in self.map.rooms
        
        room = self.map.get_or_create_room(
            room_id=room_id,
            name=name,
            area=area,
            environment=environment,
        )
        
        if description:
            room.description = description
        if tags:
            room.tags = list(set(room.tags + tags))
        
        self._auto_save()
        
        return MapUpdateResult(
            success=True,
            tool_name="add_room",
            message=f"{'Added' if is_new else 'Updated'} room: {name}",
            data={"room_id": room_id, "is_new": is_new}
        )
    
    def _tool_add_exit(
        self,
        from_room_id: str,
        to_room_id: str,
        direction: str,
        bidirectional: bool = True,
    ) -> MapUpdateResult:
        """Add an exit between rooms."""
        self.map.add_edge(
            from_room_id=from_room_id,
            to_room_id=to_room_id,
            direction=direction,
            bidirectional=bidirectional,
        )
        
        self._auto_save()
        
        return MapUpdateResult(
            success=True,
            tool_name="add_exit",
            message=f"Added exit: {from_room_id} -> {direction} -> {to_room_id}",
            data={
                "from_room_id": from_room_id,
                "to_room_id": to_room_id,
                "direction": direction
            }
        )
    
    def _tool_add_item(
        self,
        room_id: str,
        name: str,
        description: str = "",
        quantity: int = 1,
    ) -> MapUpdateResult:
        """Add an item to a room."""
        room = self.map.get_room(room_id)
        if not room:
            return MapUpdateResult(
                success=False,
                tool_name="add_item",
                message=f"Room not found: {room_id}"
            )
        
        item = RoomItem(
            name=name,
            description=description,
            quantity=quantity,
        )
        room.add_item(item)
        
        self._auto_save()
        
        return MapUpdateResult(
            success=True,
            tool_name="add_item",
            message=f"Added item '{name}' to room {room_id}",
            data={"room_id": room_id, "item": name}
        )
    
    def _tool_remove_item(self, room_id: str, name: str) -> MapUpdateResult:
        """Remove an item from a room."""
        room = self.map.get_room(room_id)
        if not room:
            return MapUpdateResult(
                success=False,
                tool_name="remove_item",
                message=f"Room not found: {room_id}"
            )
        
        if room.remove_item(name):
            self._auto_save()
            return MapUpdateResult(
                success=True,
                tool_name="remove_item",
                message=f"Removed item '{name}' from room {room_id}"
            )
        
        return MapUpdateResult(
            success=False,
            tool_name="remove_item",
            message=f"Item '{name}' not found in room {room_id}"
        )
    
    def _tool_add_npc(
        self,
        room_id: str,
        name: str,
        description: str = "",
        level: str = "",
        hostile: bool = False,
    ) -> MapUpdateResult:
        """Add an NPC to a room."""
        room = self.map.get_room(room_id)
        if not room:
            return MapUpdateResult(
                success=False,
                tool_name="add_npc",
                message=f"Room not found: {room_id}"
            )
        
        npc = RoomNPC(
            name=name,
            description=description,
            level=level,
            hostile=hostile,
        )
        room.add_npc(npc)
        
        self._auto_save()
        
        return MapUpdateResult(
            success=True,
            tool_name="add_npc",
            message=f"Added NPC '{name}' to room {room_id}",
            data={"room_id": room_id, "npc": name}
        )
    
    def _tool_remove_npc(self, room_id: str, name: str) -> MapUpdateResult:
        """Remove an NPC from a room."""
        room = self.map.get_room(room_id)
        if not room:
            return MapUpdateResult(
                success=False,
                tool_name="remove_npc",
                message=f"Room not found: {room_id}"
            )
        
        if room.remove_npc(name):
            self._auto_save()
            return MapUpdateResult(
                success=True,
                tool_name="remove_npc",
                message=f"Removed NPC '{name}' from room {room_id}"
            )
        
        return MapUpdateResult(
            success=False,
            tool_name="remove_npc",
            message=f"NPC '{name}' not found in room {room_id}"
        )
    
    def _tool_set_current_room(self, room_id: str) -> MapUpdateResult:
        """Set the current room."""
        if self.map.set_current_room(room_id):
            self.context.current_room_id = room_id
            room = self.map.get_room(room_id)
            if room:
                self.context.current_room_name = room.name
                self.context.current_area = room.area
            
            return MapUpdateResult(
                success=True,
                tool_name="set_current_room",
                message=f"Current room set to: {room_id}"
            )
        
        return MapUpdateResult(
            success=False,
            tool_name="set_current_room",
            message=f"Room not found: {room_id}"
        )
    
    def _tool_add_room_tag(self, room_id: str, tag: str) -> MapUpdateResult:
        """Add a tag to a room."""
        room = self.map.get_room(room_id)
        if not room:
            return MapUpdateResult(
                success=False,
                tool_name="add_room_tag",
                message=f"Room not found: {room_id}"
            )
        
        if tag not in room.tags:
            room.tags.append(tag)
            self._auto_save()
        
        return MapUpdateResult(
            success=True,
            tool_name="add_room_tag",
            message=f"Added tag '{tag}' to room {room_id}"
        )
    
    def _tool_add_room_note(self, room_id: str, note: str) -> MapUpdateResult:
        """Add a note to a room."""
        room = self.map.get_room(room_id)
        if not room:
            return MapUpdateResult(
                success=False,
                tool_name="add_room_note",
                message=f"Room not found: {room_id}"
            )
        
        if room.notes:
            room.notes += f"\n{note}"
        else:
            room.notes = note
        
        self._auto_save()
        
        return MapUpdateResult(
            success=True,
            tool_name="add_room_note",
            message=f"Added note to room {room_id}"
        )
    
    def _tool_set_room_image(
        self,
        room_id: str,
        image_path: Optional[str] = None,
        image_prompt: Optional[str] = None,
    ) -> MapUpdateResult:
        """Set room image info."""
        room = self.map.get_room(room_id)
        if not room:
            return MapUpdateResult(
                success=False,
                tool_name="set_room_image",
                message=f"Room not found: {room_id}"
            )
        
        if image_path:
            room.image_path = image_path
        if image_prompt:
            room.image_prompt = image_prompt
        
        self._auto_save()
        
        return MapUpdateResult(
            success=True,
            tool_name="set_room_image",
            message=f"Updated image info for room {room_id}"
        )
    
    def _tool_find_route(
        self,
        to_room_id: str,
        from_room_id: Optional[str] = None,
    ) -> MapUpdateResult:
        """Find a route between rooms."""
        start = from_room_id or self.map.current_room_id
        
        if not start:
            return MapUpdateResult(
                success=False,
                tool_name="find_route",
                message="No starting room specified and no current room set"
            )
        
        route = self.map.get_route_commands(start, to_room_id)
        
        if route is None:
            return MapUpdateResult(
                success=False,
                tool_name="find_route",
                message=f"No route found from {start} to {to_room_id}"
            )
        
        directions = self.map.find_path(start, to_room_id)
        
        return MapUpdateResult(
            success=True,
            tool_name="find_route",
            message=f"Route found: {route}",
            data={
                "route": route,
                "directions": directions,
                "steps": len(directions) if directions else 0
            }
        )
    
    def _tool_find_nearest_tagged(self, tag: str) -> MapUpdateResult:
        """Find nearest room with a tag."""
        if not self.map.current_room_id:
            return MapUpdateResult(
                success=False,
                tool_name="find_nearest_tagged",
                message="No current room set"
            )
        
        result = self.map.find_nearest_by_tag(self.map.current_room_id, tag)
        
        if not result:
            return MapUpdateResult(
                success=False,
                tool_name="find_nearest_tagged",
                message=f"No room with tag '{tag}' found"
            )
        
        room_id, path = result
        room = self.map.get_room(room_id)
        
        return MapUpdateResult(
            success=True,
            tool_name="find_nearest_tagged",
            message=f"Nearest '{tag}': {room.name if room else room_id}",
            data={
                "room_id": room_id,
                "room_name": room.name if room else "",
                "path": path,
                "steps": len(path)
            }
        )
    
    def _auto_save(self) -> None:
        """Auto-save map if enabled."""
        if self.auto_save and self.map_path:
            try:
                self.map.save_json(self.map_path)
            except Exception as e:
                logger.warning(f"Auto-save failed: {e}")

    # ==================== Direct Updates ====================
    
    def update_from_gmcp(
        self,
        room_id: str,
        room_name: str,
        area: str,
        environment: str,
        exits: dict[str, str],
        room_text: str = "",
    ) -> list[MapUpdateResult]:
        """
        Update map directly from GMCP data.
        This is the primary method for automatic mapping.
        """
        results = []
        
        # Track movement
        if self.context.current_room_id and self.context.current_room_id != room_id:
            self.context.previous_room_id = self.context.current_room_id
        
        # Add/update room
        result = self._tool_add_room(
            room_id=room_id,
            name=room_name,
            area=area,
            environment=environment,
            description=room_text,
        )
        results.append(result)
        
        # Set current room
        result = self._tool_set_current_room(room_id)
        results.append(result)
        
        # Add exits
        for direction, target_id in exits.items():
            result = self._tool_add_exit(
                from_room_id=room_id,
                to_room_id=target_id,
                direction=direction,
            )
            results.append(result)
        
        # Update context
        self.context.current_room_id = room_id
        self.context.current_room_name = room_name
        self.context.current_area = area
        self.context.current_environment = environment
        self.context.current_exits = list(exits.keys())
        self.context.room_description = room_text
        
        return results
    
    def record_movement(self, direction: str, new_room_id: str) -> None:
        """Record a movement from one room to another."""
        if self.context.current_room_id and self.context.current_room_id != new_room_id:
            self._tool_add_exit(
                from_room_id=self.context.current_room_id,
                to_room_id=new_room_id,
                direction=direction,
            )
            self.context.recent_movement = direction
            self.context.previous_room_id = self.context.current_room_id

    # ==================== LLM-Based Analysis ====================
    
    async def analyze_room_text(self, room_text: str) -> list[MapUpdateResult]:
        """
        Use LLM to analyze room text and extract map information.
        Returns list of tool call results.
        """
        import time
        
        # Rate limiting
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        
        if not self.context.current_room_id:
            logger.warning("No current room set, skipping analysis")
            return []
        
        try:
            tool_calls = await self._get_llm_tool_calls(room_text)
            self._last_request_time = time.time()
            
            results = []
            for tool_call in tool_calls:
                result = self.execute_tool(tool_call["name"], tool_call["arguments"])
                results.append(result)
                logger.debug(f"Tool result: {result.message}")
            
            return results
            
        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            return []
    
    async def _get_llm_tool_calls(self, room_text: str) -> list[dict]:
        """Get tool calls from LLM based on room text."""
        client = self._get_client()
        
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(room_text)
        
        if self.provider_name == "openai":
            return await self._get_openai_tool_calls(client, system_prompt, user_prompt)
        else:
            return await self._get_anthropic_tool_calls(client, system_prompt, user_prompt)
    
    async def _get_openai_tool_calls(
        self,
        client,
        system_prompt: str,
        user_prompt: str,
    ) -> list[dict]:
        """Get tool calls using OpenAI API."""
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
            for tool in MAP_TOOLS
        ]
        
        response = await client.chat.completions.create(
            model=self.model or "gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
        )
        
        tool_calls = []
        message = response.choices[0].message
        
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })
        
        return tool_calls
    
    async def _get_anthropic_tool_calls(
        self,
        client,
        system_prompt: str,
        user_prompt: str,
    ) -> list[dict]:
        """Get tool calls using Anthropic API."""
        # Convert tools to Anthropic format
        tools = [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"],
            }
            for tool in MAP_TOOLS
        ]
        
        response = await client.messages.create(
            model=self.model or "claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            tools=tools,
            temperature=0.1,
        )
        
        tool_calls = []
        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append({
                    "name": block.name,
                    "arguments": block.input,
                })
        
        return tool_calls
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for map analysis."""
        return """You are a mapping agent for a MUD (Multi-User Dungeon) text game.
Your task is to analyze room descriptions and extract useful information to update the world map.

You have access to tools to:
- Add rooms with their properties
- Add items and NPCs found in rooms
- Add tags to categorize rooms (shop, inn, dangerous, etc.)
- Add notes for important observations

IMPORTANT:
- Only extract information that is clearly stated in the text
- Use the current room ID for any room-specific updates
- Look for NPCs, items, special features, and notable characteristics
- Tag rooms appropriately (shop, bank, inn, quest, dangerous, etc.)
- Note any important observations

Be conservative - only make tool calls when you have clear information to add."""
    
    def _build_user_prompt(self, room_text: str) -> str:
        """Build user prompt with current context."""
        prompt = f"""Current Room Information:
- Room ID: {self.context.current_room_id}
- Room Name: {self.context.current_room_name}
- Area: {self.context.current_area}
- Environment: {self.context.current_environment}
- Exits: {', '.join(self.context.current_exits)}

Room Description:
{room_text}

Analyze this room and use tools to update the map with any relevant information (items, NPCs, tags, notes)."""
        
        return prompt

    # ==================== Navigation ====================
    
    def get_route_to(self, destination: str) -> Optional[dict]:
        """
        Get route to a destination (room ID, room name, or tag).
        Returns route info or None.
        """
        if not self.map.current_room_id:
            return None
        
        # Try as room ID first
        if destination in self.map.rooms:
            result = self._tool_find_route(destination)
            if result.success:
                return result.data
        
        # Try as room name
        rooms = self.map.find_rooms_by_name(destination)
        if rooms:
            result = self._tool_find_route(rooms[0].room_id)
            if result.success:
                return result.data
        
        # Try as tag
        result = self._tool_find_nearest_tagged(destination)
        if result.success:
            return result.data
        
        return None
    
    def get_current_room_info(self) -> Optional[dict]:
        """Get information about the current room."""
        room = self.map.get_current_room()
        if not room:
            return None
        
        return {
            "room_id": room.room_id,
            "name": room.name,
            "area": room.area,
            "environment": room.environment,
            "description": room.description,
            "exits": room.exits,
            "items": [{"name": i.name, "quantity": i.quantity} for i in room.items],
            "npcs": [{"name": n.name, "hostile": n.hostile} for n in room.npcs],
            "tags": room.tags,
            "notes": room.notes,
            "visit_count": room.visit_count,
            "image_path": room.image_path,
            "is_current": True,
        }
    
    def get_adjacent_rooms_info(self) -> list[dict]:
        """Get information about adjacent rooms."""
        if not self.map.current_room_id:
            return []
        
        adjacent = self.map.get_adjacent_rooms(self.map.current_room_id)
        result = []
        
        for direction, room_id, room_name in adjacent:
            room = self.map.get_room(room_id)
            result.append({
                "direction": direction,
                "room_id": room_id,
                "name": room_name,
                "area": room.area if room else "",
                "visited": room.visit_count > 0 if room else False,
            })
        
        return result

    # ==================== Map State ====================
    
    def save_map(self, path: Optional[str] = None) -> bool:
        """Save the map to disk."""
        save_path = Path(path) if path else self.map_path
        if not save_path:
            logger.error("No save path specified")
            return False
        
        try:
            self.map.save_json(save_path)
            return True
        except Exception as e:
            logger.error(f"Failed to save map: {e}")
            return False
    
    def load_map(self, path: Optional[str] = None) -> bool:
        """Load the map from disk."""
        load_path = Path(path) if path else self.map_path
        if not load_path or not load_path.exists():
            logger.error(f"Map file not found: {load_path}")
            return False
        
        try:
            self.map = MapGraph.load_json(load_path)
            return True
        except Exception as e:
            logger.error(f"Failed to load map: {e}")
            return False
    
    def get_map_stats(self) -> dict:
        """Get map statistics."""
        stats = self.map.get_stats()
        stats["current_room"] = self.get_current_room_info()
        return stats
    
    def get_map_data_for_visualization(self) -> dict:
        """Get map data suitable for frontend visualization."""
        # Auto-layout if no positions set
        has_positions = any(
            r.x is not None and r.y is not None 
            for r in self.map.rooms.values()
        )
        
        if not has_positions:
            self.map.auto_layout()
        
        rooms = []
        for room in self.map.rooms.values():
            rooms.append({
                "id": room.room_id,
                "name": room.name,
                "area": room.area,
                "environment": room.environment,
                "x": room.x or 0,
                "y": room.y or 0,
                "z": room.z or 0,
                "exits": room.exits,
                "tags": room.tags,
                "visit_count": room.visit_count,
                "is_current": room.room_id == self.map.current_room_id,
                "has_items": len(room.items) > 0,
                "has_npcs": len(room.npcs) > 0,
                "has_image": room.image_path is not None,
            })
        
        edges = []
        for edge in self.map.edges:
            edges.append({
                "from": edge.from_room,
                "to": edge.to_room,
                "direction": edge.direction,
                "bidirectional": edge.bidirectional,
            })
        
        return {
            "rooms": rooms,
            "edges": edges,
            "current_room_id": self.map.current_room_id,
            "stats": self.map.get_stats(),
        }
    
    def export_graphviz(self) -> str:
        """Export map as Graphviz DOT format."""
        lines = ["digraph MUDMap {"]
        lines.append("  rankdir=TB;")
        lines.append("  node [shape=box];")
        
        # Add rooms
        for room in self.map.rooms.values():
            label = room.name.replace('"', '\\"')
            style = 'style=filled,fillcolor=lightblue' if room.room_id == self.map.current_room_id else ''
            lines.append(f'  "{room.room_id}" [label="{label}" {style}];')
        
        # Add edges
        seen = set()
        for edge in self.map.edges:
            edge_key = (edge.from_room, edge.to_room)
            if edge_key not in seen:
                lines.append(f'  "{edge.from_room}" -> "{edge.to_room}" [label="{edge.direction}"];')
                seen.add(edge_key)
        
        lines.append("}")
        return "\n".join(lines)
