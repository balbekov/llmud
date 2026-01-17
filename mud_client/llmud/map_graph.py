"""
Map Graph - Graph-based world map for MUD navigation and mapping.

This module provides:
- Room nodes with metadata (text, items, images, etc.)
- Directional edges between rooms
- Pathfinding (A*, BFS, Dijkstra)
- Serialization to/from disk (JSON/pickle)
- Current room tracking
"""

import json
import heapq
import logging
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from collections import deque
from enum import Enum
import pickle

logger = logging.getLogger(__name__)


class Direction(Enum):
    """Standard MUD directions."""
    NORTH = "n"
    SOUTH = "s"
    EAST = "e"
    WEST = "w"
    NORTHEAST = "ne"
    NORTHWEST = "nw"
    SOUTHEAST = "se"
    SOUTHWEST = "sw"
    UP = "u"
    DOWN = "d"
    ENTER = "enter"
    OUT = "out"
    
    @classmethod
    def from_string(cls, direction: str) -> Optional["Direction"]:
        """Convert string to Direction enum."""
        direction = direction.lower().strip()
        
        # Handle full names
        name_map = {
            "north": cls.NORTH,
            "south": cls.SOUTH,
            "east": cls.EAST,
            "west": cls.WEST,
            "northeast": cls.NORTHEAST,
            "northwest": cls.NORTHWEST,
            "southeast": cls.SOUTHEAST,
            "southwest": cls.SOUTHWEST,
            "up": cls.UP,
            "down": cls.DOWN,
            "enter": cls.ENTER,
            "out": cls.OUT,
        }
        
        if direction in name_map:
            return name_map[direction]
        
        # Handle abbreviations
        for d in cls:
            if d.value == direction:
                return d
        
        return None
    
    @classmethod
    def get_opposite(cls, direction: "Direction") -> Optional["Direction"]:
        """Get the opposite direction."""
        opposites = {
            cls.NORTH: cls.SOUTH,
            cls.SOUTH: cls.NORTH,
            cls.EAST: cls.WEST,
            cls.WEST: cls.EAST,
            cls.NORTHEAST: cls.SOUTHWEST,
            cls.SOUTHWEST: cls.NORTHEAST,
            cls.NORTHWEST: cls.SOUTHEAST,
            cls.SOUTHEAST: cls.NORTHWEST,
            cls.UP: cls.DOWN,
            cls.DOWN: cls.UP,
            cls.ENTER: cls.OUT,
            cls.OUT: cls.ENTER,
        }
        return opposites.get(direction)


@dataclass
class RoomItem:
    """An item found in a room."""
    name: str
    description: str = ""
    quantity: int = 1
    last_seen: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "quantity": self.quantity,
            "last_seen": self.last_seen.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RoomItem":
        data = data.copy()
        if "last_seen" in data:
            data["last_seen"] = datetime.fromisoformat(data["last_seen"])
        return cls(**data)


@dataclass
class RoomNPC:
    """An NPC found in a room."""
    name: str
    description: str = ""
    level: str = ""  # "easy", "medium", "hard", etc.
    hostile: bool = False
    last_seen: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "level": self.level,
            "hostile": self.hostile,
            "last_seen": self.last_seen.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RoomNPC":
        data = data.copy()
        if "last_seen" in data:
            data["last_seen"] = datetime.fromisoformat(data["last_seen"])
        return cls(**data)


@dataclass
class RoomNode:
    """A room in the MUD world map."""
    room_id: str
    name: str
    area: str = ""
    environment: str = ""
    description: str = ""
    
    # Exits (direction -> target room_id)
    exits: dict[str, str] = field(default_factory=dict)
    
    # Room contents
    items: list[RoomItem] = field(default_factory=list)
    npcs: list[RoomNPC] = field(default_factory=list)
    
    # Metadata
    tags: list[str] = field(default_factory=list)  # e.g., ["shop", "inn", "dangerous"]
    notes: str = ""
    
    # Visit tracking
    visit_count: int = 0
    first_visited: datetime = field(default_factory=datetime.now)
    last_visited: datetime = field(default_factory=datetime.now)
    
    # Image generation
    image_path: Optional[str] = None
    image_prompt: Optional[str] = None
    
    # Coordinates for visualization (optional, can be auto-calculated)
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None  # For multi-level maps
    
    def add_exit(self, direction: str, target_room_id: str) -> None:
        """Add or update an exit."""
        self.exits[direction] = target_room_id
    
    def remove_exit(self, direction: str) -> bool:
        """Remove an exit. Returns True if it existed."""
        if direction in self.exits:
            del self.exits[direction]
            return True
        return False
    
    def add_item(self, item: RoomItem) -> None:
        """Add an item to the room."""
        # Check if item already exists, update if so
        for i, existing in enumerate(self.items):
            if existing.name.lower() == item.name.lower():
                self.items[i] = item
                return
        self.items.append(item)
    
    def remove_item(self, item_name: str) -> bool:
        """Remove an item by name. Returns True if found."""
        for i, item in enumerate(self.items):
            if item.name.lower() == item_name.lower():
                del self.items[i]
                return True
        return False
    
    def add_npc(self, npc: RoomNPC) -> None:
        """Add an NPC to the room."""
        for i, existing in enumerate(self.npcs):
            if existing.name.lower() == npc.name.lower():
                self.npcs[i] = npc
                return
        self.npcs.append(npc)
    
    def remove_npc(self, npc_name: str) -> bool:
        """Remove an NPC by name. Returns True if found."""
        for i, npc in enumerate(self.npcs):
            if npc.name.lower() == npc_name.lower():
                del self.npcs[i]
                return True
        return False
    
    def record_visit(self) -> None:
        """Record a visit to this room."""
        self.visit_count += 1
        self.last_visited = datetime.now()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "room_id": self.room_id,
            "name": self.name,
            "area": self.area,
            "environment": self.environment,
            "description": self.description,
            "exits": self.exits.copy(),
            "items": [item.to_dict() for item in self.items],
            "npcs": [npc.to_dict() for npc in self.npcs],
            "tags": self.tags.copy(),
            "notes": self.notes,
            "visit_count": self.visit_count,
            "first_visited": self.first_visited.isoformat(),
            "last_visited": self.last_visited.isoformat(),
            "image_path": self.image_path,
            "image_prompt": self.image_prompt,
            "x": self.x,
            "y": self.y,
            "z": self.z,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RoomNode":
        """Create from dictionary."""
        data = data.copy()
        
        # Convert datetime strings
        if "first_visited" in data:
            data["first_visited"] = datetime.fromisoformat(data["first_visited"])
        if "last_visited" in data:
            data["last_visited"] = datetime.fromisoformat(data["last_visited"])
        
        # Convert items and NPCs
        if "items" in data:
            data["items"] = [RoomItem.from_dict(i) for i in data["items"]]
        if "npcs" in data:
            data["npcs"] = [RoomNPC.from_dict(n) for n in data["npcs"]]
        
        return cls(**data)


@dataclass
class MapEdge:
    """An edge (connection) between two rooms."""
    from_room: str
    to_room: str
    direction: str
    cost: float = 1.0  # For weighted pathfinding
    bidirectional: bool = True
    blocked: bool = False  # e.g., locked doors
    notes: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "MapEdge":
        return cls(**data)


class MapGraph:
    """
    Graph-based world map with pathfinding support.
    
    Features:
    - Room nodes with full metadata
    - Directional edges with costs
    - Multiple pathfinding algorithms
    - Serialization to/from disk
    - Current room tracking
    - Area-based organization
    """
    
    def __init__(self, name: str = "world"):
        self.name = name
        self.rooms: dict[str, RoomNode] = {}
        self.edges: list[MapEdge] = []
        self.current_room_id: Optional[str] = None
        
        # Index for fast edge lookups
        self._edge_index: dict[str, dict[str, MapEdge]] = {}  # room_id -> {direction -> edge}
        
        # Metadata
        self.created_at: datetime = datetime.now()
        self.last_modified: datetime = datetime.now()
        self.version: str = "1.0"
    
    # ==================== Room Operations ====================
    
    def add_room(self, room: RoomNode, set_current: bool = False) -> None:
        """Add a room to the map."""
        self.rooms[room.room_id] = room
        self.last_modified = datetime.now()
        
        if set_current:
            self.current_room_id = room.room_id
        
        # Initialize edge index for this room
        if room.room_id not in self._edge_index:
            self._edge_index[room.room_id] = {}
        
        logger.debug(f"Added room: {room.name} ({room.room_id})")
    
    def get_room(self, room_id: str) -> Optional[RoomNode]:
        """Get a room by ID."""
        return self.rooms.get(room_id)
    
    def update_room(
        self,
        room_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        area: Optional[str] = None,
        environment: Optional[str] = None,
        tags: Optional[list[str]] = None,
        notes: Optional[str] = None,
        image_path: Optional[str] = None,
        image_prompt: Optional[str] = None,
    ) -> bool:
        """Update room properties. Returns True if room exists."""
        room = self.rooms.get(room_id)
        if not room:
            return False
        
        if name is not None:
            room.name = name
        if description is not None:
            room.description = description
        if area is not None:
            room.area = area
        if environment is not None:
            room.environment = environment
        if tags is not None:
            room.tags = tags
        if notes is not None:
            room.notes = notes
        if image_path is not None:
            room.image_path = image_path
        if image_prompt is not None:
            room.image_prompt = image_prompt
        
        self.last_modified = datetime.now()
        return True
    
    def remove_room(self, room_id: str) -> bool:
        """Remove a room and all its edges. Returns True if it existed."""
        if room_id not in self.rooms:
            return False
        
        # Remove room
        del self.rooms[room_id]
        
        # Remove all edges to/from this room
        self.edges = [e for e in self.edges 
                      if e.from_room != room_id and e.to_room != room_id]
        
        # Update edge index
        if room_id in self._edge_index:
            del self._edge_index[room_id]
        
        for rid, directions in self._edge_index.items():
            to_remove = [d for d, e in directions.items() if e.to_room == room_id]
            for d in to_remove:
                del directions[d]
        
        # Update current room if needed
        if self.current_room_id == room_id:
            self.current_room_id = None
        
        self.last_modified = datetime.now()
        return True
    
    def get_or_create_room(
        self,
        room_id: str,
        name: str = "",
        area: str = "",
        environment: str = "",
    ) -> RoomNode:
        """Get existing room or create a new one."""
        if room_id in self.rooms:
            room = self.rooms[room_id]
            # Update fields if provided
            if name:
                room.name = name
            if area:
                room.area = area
            if environment:
                room.environment = environment
            return room
        
        # Create new room
        room = RoomNode(
            room_id=room_id,
            name=name or f"Room {room_id}",
            area=area,
            environment=environment,
        )
        self.add_room(room)
        return room
    
    # ==================== Edge Operations ====================
    
    def add_edge(
        self,
        from_room_id: str,
        to_room_id: str,
        direction: str,
        cost: float = 1.0,
        bidirectional: bool = True,
    ) -> MapEdge:
        """Add an edge between rooms."""
        # Ensure rooms exist
        if from_room_id not in self.rooms:
            logger.warning(f"Source room {from_room_id} not found, creating placeholder")
            self.add_room(RoomNode(room_id=from_room_id, name=f"Room {from_room_id}"))
        
        if to_room_id not in self.rooms:
            logger.warning(f"Target room {to_room_id} not found, creating placeholder")
            self.add_room(RoomNode(room_id=to_room_id, name=f"Room {to_room_id}"))
        
        # Create edge
        edge = MapEdge(
            from_room=from_room_id,
            to_room=to_room_id,
            direction=direction,
            cost=cost,
            bidirectional=bidirectional,
        )
        
        # Update room exits
        self.rooms[from_room_id].add_exit(direction, to_room_id)
        
        # Add reverse edge if bidirectional
        if bidirectional:
            dir_enum = Direction.from_string(direction)
            if dir_enum:
                opposite = Direction.get_opposite(dir_enum)
                if opposite:
                    self.rooms[to_room_id].add_exit(opposite.value, from_room_id)
        
        # Add to edge list
        self.edges.append(edge)
        
        # Update index
        if from_room_id not in self._edge_index:
            self._edge_index[from_room_id] = {}
        self._edge_index[from_room_id][direction] = edge
        
        self.last_modified = datetime.now()
        return edge
    
    def remove_edge(self, from_room_id: str, direction: str) -> bool:
        """Remove an edge. Returns True if it existed."""
        if from_room_id not in self._edge_index:
            return False
        
        if direction not in self._edge_index[from_room_id]:
            return False
        
        edge = self._edge_index[from_room_id][direction]
        
        # Remove from room exits
        if from_room_id in self.rooms:
            self.rooms[from_room_id].remove_exit(direction)
        
        # Remove reverse if bidirectional
        if edge.bidirectional and edge.to_room in self.rooms:
            dir_enum = Direction.from_string(direction)
            if dir_enum:
                opposite = Direction.get_opposite(dir_enum)
                if opposite:
                    self.rooms[edge.to_room].remove_exit(opposite.value)
        
        # Remove from edge list
        self.edges.remove(edge)
        
        # Update index
        del self._edge_index[from_room_id][direction]
        
        self.last_modified = datetime.now()
        return True
    
    def get_edge(self, from_room_id: str, direction: str) -> Optional[MapEdge]:
        """Get an edge by room and direction."""
        if from_room_id not in self._edge_index:
            return None
        return self._edge_index[from_room_id].get(direction)
    
    def get_adjacent_rooms(self, room_id: str) -> list[tuple[str, str, str]]:
        """Get all adjacent rooms. Returns list of (direction, room_id, room_name)."""
        room = self.rooms.get(room_id)
        if not room:
            return []
        
        adjacent = []
        for direction, target_id in room.exits.items():
            target = self.rooms.get(target_id)
            target_name = target.name if target else f"Unknown ({target_id})"
            adjacent.append((direction, target_id, target_name))
        
        return adjacent
    
    # ==================== Current Room ====================
    
    def set_current_room(self, room_id: str) -> bool:
        """Set the current room. Returns True if room exists."""
        if room_id not in self.rooms:
            return False
        
        self.current_room_id = room_id
        self.rooms[room_id].record_visit()
        return True
    
    def get_current_room(self) -> Optional[RoomNode]:
        """Get the current room."""
        if self.current_room_id:
            return self.rooms.get(self.current_room_id)
        return None
    
    def move(self, direction: str) -> Optional[RoomNode]:
        """
        Move in a direction from the current room.
        Returns the new room if successful, None otherwise.
        """
        if not self.current_room_id:
            return None
        
        current = self.rooms.get(self.current_room_id)
        if not current:
            return None
        
        direction = direction.lower()
        
        if direction not in current.exits:
            return None
        
        target_id = current.exits[direction]
        target = self.rooms.get(target_id)
        
        if target:
            self.current_room_id = target_id
            target.record_visit()
            return target
        
        return None
    
    # ==================== Pathfinding ====================
    
    def find_path_bfs(
        self,
        from_room_id: str,
        to_room_id: str,
    ) -> Optional[list[tuple[str, str]]]:
        """
        Find shortest path using BFS.
        Returns list of (direction, room_id) tuples, or None if no path.
        """
        if from_room_id not in self.rooms or to_room_id not in self.rooms:
            return None
        
        if from_room_id == to_room_id:
            return []
        
        # BFS
        queue = deque([(from_room_id, [])])
        visited = {from_room_id}
        
        while queue:
            current_id, path = queue.popleft()
            current = self.rooms.get(current_id)
            
            if not current:
                continue
            
            for direction, target_id in current.exits.items():
                if target_id == to_room_id:
                    return path + [(direction, target_id)]
                
                if target_id not in visited and target_id in self.rooms:
                    visited.add(target_id)
                    queue.append((target_id, path + [(direction, target_id)]))
        
        return None
    
    def find_path_astar(
        self,
        from_room_id: str,
        to_room_id: str,
        heuristic: Optional[callable] = None,
    ) -> Optional[list[tuple[str, str, float]]]:
        """
        Find path using A* algorithm with optional heuristic.
        Returns list of (direction, room_id, cumulative_cost) tuples.
        """
        if from_room_id not in self.rooms or to_room_id not in self.rooms:
            return None
        
        if from_room_id == to_room_id:
            return []
        
        # Default heuristic (returns 0 - becomes Dijkstra)
        if heuristic is None:
            heuristic = lambda a, b: 0
        
        # Priority queue: (f_score, counter, room_id, path)
        counter = 0
        open_set = [(0, counter, from_room_id, [])]
        g_scores = {from_room_id: 0}
        
        while open_set:
            _, _, current_id, path = heapq.heappop(open_set)
            
            if current_id == to_room_id:
                return path
            
            current = self.rooms.get(current_id)
            if not current:
                continue
            
            for direction, target_id in current.exits.items():
                if target_id not in self.rooms:
                    continue
                
                # Get edge cost
                edge = self.get_edge(current_id, direction)
                edge_cost = edge.cost if edge else 1.0
                
                if edge and edge.blocked:
                    continue
                
                tentative_g = g_scores[current_id] + edge_cost
                
                if target_id not in g_scores or tentative_g < g_scores[target_id]:
                    g_scores[target_id] = tentative_g
                    f_score = tentative_g + heuristic(target_id, to_room_id)
                    counter += 1
                    new_path = path + [(direction, target_id, tentative_g)]
                    heapq.heappush(open_set, (f_score, counter, target_id, new_path))
        
        return None
    
    def find_path(
        self,
        from_room_id: str,
        to_room_id: str,
    ) -> Optional[list[str]]:
        """
        Find path and return just the directions to follow.
        Convenience method that uses BFS.
        """
        path = self.find_path_bfs(from_room_id, to_room_id)
        if path is None:
            return None
        return [step[0] for step in path]
    
    def get_route_commands(
        self,
        from_room_id: str,
        to_room_id: str,
    ) -> Optional[str]:
        """
        Get route as a MUD speedwalk command string.
        Example: "3n2e;s;enter"
        """
        directions = self.find_path(from_room_id, to_room_id)
        if directions is None:
            return None
        
        if not directions:
            return ""
        
        # Compress repeated directions
        result = []
        count = 1
        prev = directions[0]
        
        for d in directions[1:]:
            if d == prev:
                count += 1
            else:
                if count > 1:
                    result.append(f"{count}{prev}")
                else:
                    result.append(prev)
                prev = d
                count = 1
        
        # Don't forget the last direction
        if count > 1:
            result.append(f"{count}{prev}")
        else:
            result.append(prev)
        
        return ";".join(result)
    
    # ==================== Search & Query ====================
    
    def find_rooms_by_area(self, area: str) -> list[RoomNode]:
        """Find all rooms in an area."""
        return [r for r in self.rooms.values() 
                if r.area.lower() == area.lower()]
    
    def find_rooms_by_tag(self, tag: str) -> list[RoomNode]:
        """Find all rooms with a specific tag."""
        return [r for r in self.rooms.values() 
                if tag.lower() in [t.lower() for t in r.tags]]
    
    def find_rooms_by_name(self, name: str, partial: bool = True) -> list[RoomNode]:
        """Find rooms by name (partial or exact match)."""
        name = name.lower()
        if partial:
            return [r for r in self.rooms.values() 
                    if name in r.name.lower()]
        return [r for r in self.rooms.values() 
                if r.name.lower() == name]
    
    def find_nearest_by_tag(self, from_room_id: str, tag: str) -> Optional[tuple[str, list[str]]]:
        """
        Find the nearest room with a specific tag.
        Returns (room_id, path_directions) or None.
        """
        target_rooms = self.find_rooms_by_tag(tag)
        if not target_rooms:
            return None
        
        best_path = None
        best_room = None
        
        for room in target_rooms:
            path = self.find_path(from_room_id, room.room_id)
            if path is not None:
                if best_path is None or len(path) < len(best_path):
                    best_path = path
                    best_room = room.room_id
        
        if best_room:
            return (best_room, best_path)
        return None
    
    # ==================== Statistics ====================
    
    def get_stats(self) -> dict:
        """Get map statistics."""
        areas = {}
        for room in self.rooms.values():
            area = room.area or "Unknown"
            if area not in areas:
                areas[area] = 0
            areas[area] += 1
        
        return {
            "total_rooms": len(self.rooms),
            "total_edges": len(self.edges),
            "areas": areas,
            "current_room": self.current_room_id,
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat(),
        }
    
    def get_unexplored_exits(self, room_id: Optional[str] = None) -> list[tuple[str, str]]:
        """
        Get exits that lead to unknown rooms.
        Returns list of (room_id, direction) tuples.
        """
        unexplored = []
        
        rooms_to_check = [self.rooms.get(room_id)] if room_id else self.rooms.values()
        
        for room in rooms_to_check:
            if not room:
                continue
            for direction, target_id in room.exits.items():
                if target_id not in self.rooms:
                    unexplored.append((room.room_id, direction))
        
        return unexplored
    
    # ==================== Serialization ====================
    
    def to_dict(self) -> dict:
        """Convert map to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat(),
            "current_room_id": self.current_room_id,
            "rooms": {rid: room.to_dict() for rid, room in self.rooms.items()},
            "edges": [e.to_dict() for e in self.edges],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "MapGraph":
        """Create map from dictionary."""
        map_graph = cls(name=data.get("name", "world"))
        map_graph.version = data.get("version", "1.0")
        map_graph.current_room_id = data.get("current_room_id")
        
        if "created_at" in data:
            map_graph.created_at = datetime.fromisoformat(data["created_at"])
        if "last_modified" in data:
            map_graph.last_modified = datetime.fromisoformat(data["last_modified"])
        
        # Load rooms
        for rid, room_data in data.get("rooms", {}).items():
            room = RoomNode.from_dict(room_data)
            map_graph.rooms[rid] = room
            map_graph._edge_index[rid] = {}
        
        # Load edges and rebuild index
        for edge_data in data.get("edges", []):
            edge = MapEdge.from_dict(edge_data)
            map_graph.edges.append(edge)
            
            if edge.from_room not in map_graph._edge_index:
                map_graph._edge_index[edge.from_room] = {}
            map_graph._edge_index[edge.from_room][edge.direction] = edge
        
        return map_graph
    
    def save_json(self, path: str | Path) -> None:
        """Save map to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        
        logger.info(f"Saved map to {path} ({len(self.rooms)} rooms)")
    
    @classmethod
    def load_json(cls, path: str | Path) -> "MapGraph":
        """Load map from JSON file."""
        path = Path(path)
        
        with open(path) as f:
            data = json.load(f)
        
        map_graph = cls.from_dict(data)
        logger.info(f"Loaded map from {path} ({len(map_graph.rooms)} rooms)")
        return map_graph
    
    def save_pickle(self, path: str | Path) -> None:
        """Save map to pickle file (faster but not human-readable)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "wb") as f:
            pickle.dump(self, f)
        
        logger.info(f"Saved map (pickle) to {path}")
    
    @classmethod
    def load_pickle(cls, path: str | Path) -> "MapGraph":
        """Load map from pickle file."""
        with open(path, "rb") as f:
            map_graph = pickle.load(f)
        
        logger.info(f"Loaded map (pickle) from {path}")
        return map_graph
    
    # ==================== Auto-Layout ====================
    
    def auto_layout(self, start_room_id: Optional[str] = None) -> None:
        """
        Auto-calculate room positions for visualization.
        Uses BFS from start room to assign coordinates.
        """
        start = start_room_id or self.current_room_id
        if not start or start not in self.rooms:
            if self.rooms:
                start = next(iter(self.rooms.keys()))
            else:
                return
        
        # Direction offsets
        offsets = {
            "n": (0, -1), "s": (0, 1),
            "e": (1, 0), "w": (-1, 0),
            "ne": (1, -1), "nw": (-1, -1),
            "se": (1, 1), "sw": (-1, 1),
            "u": (0, 0, 1), "d": (0, 0, -1),
        }
        
        # BFS to assign coordinates
        queue = deque([start])
        self.rooms[start].x = 0
        self.rooms[start].y = 0
        self.rooms[start].z = 0
        visited = {start}
        
        while queue:
            current_id = queue.popleft()
            current = self.rooms.get(current_id)
            
            if not current:
                continue
            
            for direction, target_id in current.exits.items():
                if target_id in visited or target_id not in self.rooms:
                    continue
                
                target = self.rooms[target_id]
                offset = offsets.get(direction, (0, 0))
                
                target.x = (current.x or 0) + offset[0]
                target.y = (current.y or 0) + offset[1]
                
                if len(offset) == 3:
                    target.z = (current.z or 0) + offset[2]
                else:
                    target.z = current.z
                
                visited.add(target_id)
                queue.append(target_id)
