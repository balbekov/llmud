"""Tests for the mapping agent and graph system."""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

# Add the parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from llmud.map_graph import (
    MapGraph,
    RoomNode,
    RoomItem,
    RoomNPC,
    MapEdge,
    Direction,
)
from llmud.map_agent import MapAgent, MappingContext, MapUpdateResult


class TestDirection:
    """Tests for Direction enum."""
    
    def test_from_string_abbreviations(self):
        """Test converting abbreviations to Direction."""
        assert Direction.from_string("n") == Direction.NORTH
        assert Direction.from_string("s") == Direction.SOUTH
        assert Direction.from_string("e") == Direction.EAST
        assert Direction.from_string("w") == Direction.WEST
        assert Direction.from_string("ne") == Direction.NORTHEAST
        assert Direction.from_string("u") == Direction.UP
        assert Direction.from_string("d") == Direction.DOWN
    
    def test_from_string_full_names(self):
        """Test converting full names to Direction."""
        assert Direction.from_string("north") == Direction.NORTH
        assert Direction.from_string("south") == Direction.SOUTH
        assert Direction.from_string("northeast") == Direction.NORTHEAST
        assert Direction.from_string("up") == Direction.UP
    
    def test_from_string_invalid(self):
        """Test invalid direction returns None."""
        assert Direction.from_string("invalid") is None
        assert Direction.from_string("") is None
    
    def test_get_opposite(self):
        """Test getting opposite directions."""
        assert Direction.get_opposite(Direction.NORTH) == Direction.SOUTH
        assert Direction.get_opposite(Direction.SOUTH) == Direction.NORTH
        assert Direction.get_opposite(Direction.EAST) == Direction.WEST
        assert Direction.get_opposite(Direction.UP) == Direction.DOWN
        assert Direction.get_opposite(Direction.ENTER) == Direction.OUT


class TestRoomNode:
    """Tests for RoomNode class."""
    
    def test_create_room(self):
        """Test creating a basic room."""
        room = RoomNode(
            room_id="room1",
            name="Test Room",
            area="Test Area",
            environment="indoor",
            description="A test room.",
        )
        
        assert room.room_id == "room1"
        assert room.name == "Test Room"
        assert room.area == "Test Area"
        assert room.environment == "indoor"
        assert room.description == "A test room."
        assert room.visit_count == 0
        assert len(room.exits) == 0
        assert len(room.items) == 0
        assert len(room.npcs) == 0
    
    def test_add_exit(self):
        """Test adding an exit."""
        room = RoomNode(room_id="room1", name="Test")
        room.add_exit("n", "room2")
        
        assert "n" in room.exits
        assert room.exits["n"] == "room2"
    
    def test_remove_exit(self):
        """Test removing an exit."""
        room = RoomNode(room_id="room1", name="Test")
        room.add_exit("n", "room2")
        
        assert room.remove_exit("n") is True
        assert "n" not in room.exits
        assert room.remove_exit("n") is False  # Already removed
    
    def test_add_item(self):
        """Test adding an item."""
        room = RoomNode(room_id="room1", name="Test")
        item = RoomItem(name="Sword", description="A sharp sword", quantity=1)
        room.add_item(item)
        
        assert len(room.items) == 1
        assert room.items[0].name == "Sword"
        
        # Adding same item should update
        item2 = RoomItem(name="Sword", description="Updated", quantity=2)
        room.add_item(item2)
        
        assert len(room.items) == 1
        assert room.items[0].quantity == 2
    
    def test_add_npc(self):
        """Test adding an NPC."""
        room = RoomNode(room_id="room1", name="Test")
        npc = RoomNPC(name="Guard", description="A guard", hostile=True)
        room.add_npc(npc)
        
        assert len(room.npcs) == 1
        assert room.npcs[0].name == "Guard"
        assert room.npcs[0].hostile is True
    
    def test_record_visit(self):
        """Test recording visits."""
        room = RoomNode(room_id="room1", name="Test")
        assert room.visit_count == 0
        
        room.record_visit()
        assert room.visit_count == 1
        
        room.record_visit()
        assert room.visit_count == 2
    
    def test_to_dict_from_dict(self):
        """Test serialization and deserialization."""
        room = RoomNode(
            room_id="room1",
            name="Test Room",
            area="Test Area",
            description="A test room.",
            tags=["shop", "inn"],
        )
        room.add_item(RoomItem(name="Sword"))
        room.add_npc(RoomNPC(name="Guard", hostile=True))
        room.add_exit("n", "room2")
        room.record_visit()
        
        # Convert to dict and back
        room_dict = room.to_dict()
        restored = RoomNode.from_dict(room_dict)
        
        assert restored.room_id == room.room_id
        assert restored.name == room.name
        assert restored.area == room.area
        assert restored.tags == room.tags
        assert restored.visit_count == room.visit_count
        assert len(restored.items) == 1
        assert len(restored.npcs) == 1
        assert restored.exits == room.exits


class TestMapGraph:
    """Tests for MapGraph class."""
    
    def test_create_empty_map(self):
        """Test creating an empty map."""
        m = MapGraph(name="test")
        assert m.name == "test"
        assert len(m.rooms) == 0
        assert len(m.edges) == 0
        assert m.current_room_id is None
    
    def test_add_room(self):
        """Test adding rooms."""
        m = MapGraph()
        room = RoomNode(room_id="room1", name="Test Room")
        m.add_room(room)
        
        assert "room1" in m.rooms
        assert m.rooms["room1"].name == "Test Room"
    
    def test_get_or_create_room(self):
        """Test get_or_create_room."""
        m = MapGraph()
        
        # Create new room
        room = m.get_or_create_room("room1", name="Test Room", area="Area1")
        assert room.name == "Test Room"
        assert room.area == "Area1"
        
        # Get existing room (should update)
        room2 = m.get_or_create_room("room1", name="Updated", area="Area2")
        assert room2.name == "Updated"
        assert room2.area == "Area2"
        assert m.rooms["room1"] is room  # Same object
    
    def test_add_edge(self):
        """Test adding edges."""
        m = MapGraph()
        m.add_room(RoomNode(room_id="room1", name="Room 1"))
        m.add_room(RoomNode(room_id="room2", name="Room 2"))
        
        edge = m.add_edge("room1", "room2", "n")
        
        assert len(m.edges) == 1
        assert m.rooms["room1"].exits["n"] == "room2"
        # Bidirectional by default
        assert m.rooms["room2"].exits["s"] == "room1"
    
    def test_set_current_room(self):
        """Test setting current room."""
        m = MapGraph()
        room = RoomNode(room_id="room1", name="Test")
        m.add_room(room)
        
        assert m.set_current_room("room1") is True
        assert m.current_room_id == "room1"
        assert room.visit_count == 1
        
        assert m.set_current_room("nonexistent") is False
    
    def test_move(self):
        """Test moving between rooms."""
        m = MapGraph()
        m.add_room(RoomNode(room_id="room1", name="Room 1"))
        m.add_room(RoomNode(room_id="room2", name="Room 2"))
        m.add_edge("room1", "room2", "n")
        m.set_current_room("room1")
        
        # Move north
        new_room = m.move("n")
        assert new_room is not None
        assert new_room.room_id == "room2"
        assert m.current_room_id == "room2"
        
        # Move south (back)
        new_room = m.move("s")
        assert new_room is not None
        assert new_room.room_id == "room1"
        
        # Invalid direction
        assert m.move("invalid") is None
    
    def test_pathfinding_bfs(self):
        """Test BFS pathfinding."""
        m = MapGraph()
        
        # Create a simple path: room1 -> room2 -> room3
        for i in range(1, 4):
            m.add_room(RoomNode(room_id=f"room{i}", name=f"Room {i}"))
        
        m.add_edge("room1", "room2", "n")
        m.add_edge("room2", "room3", "e")
        
        path = m.find_path_bfs("room1", "room3")
        
        assert path is not None
        assert len(path) == 2
        assert path[0] == ("n", "room2")
        assert path[1] == ("e", "room3")
    
    def test_pathfinding_no_path(self):
        """Test pathfinding when no path exists."""
        m = MapGraph()
        m.add_room(RoomNode(room_id="room1", name="Room 1"))
        m.add_room(RoomNode(room_id="room2", name="Room 2"))
        # No edge between them
        
        path = m.find_path_bfs("room1", "room2")
        assert path is None
    
    def test_find_path_directions(self):
        """Test getting just directions from path."""
        m = MapGraph()
        
        for i in range(1, 4):
            m.add_room(RoomNode(room_id=f"room{i}", name=f"Room {i}"))
        
        m.add_edge("room1", "room2", "n")
        m.add_edge("room2", "room3", "e")
        
        directions = m.find_path("room1", "room3")
        
        assert directions == ["n", "e"]
    
    def test_get_route_commands(self):
        """Test generating speedwalk commands."""
        m = MapGraph()
        
        # Create path with repeated directions
        for i in range(1, 5):
            m.add_room(RoomNode(room_id=f"room{i}", name=f"Room {i}"))
        
        m.add_edge("room1", "room2", "n")
        m.add_edge("room2", "room3", "n")
        m.add_edge("room3", "room4", "e")
        
        route = m.get_route_commands("room1", "room4")
        
        assert route == "2n;e"
    
    def test_find_rooms_by_tag(self):
        """Test finding rooms by tag."""
        m = MapGraph()
        
        room1 = RoomNode(room_id="room1", name="Shop", tags=["shop"])
        room2 = RoomNode(room_id="room2", name="Inn", tags=["inn"])
        room3 = RoomNode(room_id="room3", name="General Store", tags=["shop"])
        
        m.add_room(room1)
        m.add_room(room2)
        m.add_room(room3)
        
        shops = m.find_rooms_by_tag("shop")
        assert len(shops) == 2
        
        inns = m.find_rooms_by_tag("inn")
        assert len(inns) == 1
    
    def test_find_nearest_by_tag(self):
        """Test finding nearest room with tag."""
        m = MapGraph()
        
        # Room 1 (current) -> Room 2 -> Room 3 (shop)
        #                  -> Room 4 (shop, closer)
        for i in range(1, 5):
            tags = ["shop"] if i in [3, 4] else []
            m.add_room(RoomNode(room_id=f"room{i}", name=f"Room {i}", tags=tags))
        
        m.add_edge("room1", "room2", "n")
        m.add_edge("room2", "room3", "e")
        m.add_edge("room1", "room4", "s")  # Shorter path
        m.set_current_room("room1")
        
        result = m.find_nearest_by_tag("room1", "shop")
        assert result is not None
        room_id, path = result
        assert room_id == "room4"  # Closer shop
        assert path == ["s"]
    
    def test_json_serialization(self):
        """Test saving and loading map as JSON."""
        m = MapGraph(name="test_map")
        
        room1 = RoomNode(room_id="room1", name="Room 1", area="Area1")
        room1.add_item(RoomItem(name="Sword"))
        room2 = RoomNode(room_id="room2", name="Room 2")
        
        m.add_room(room1)
        m.add_room(room2)
        m.add_edge("room1", "room2", "n")
        m.set_current_room("room1")
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        
        try:
            m.save_json(temp_path)
            
            # Load back
            loaded = MapGraph.load_json(temp_path)
            
            assert loaded.name == "test_map"
            assert len(loaded.rooms) == 2
            assert loaded.current_room_id == "room1"
            assert len(loaded.rooms["room1"].items) == 1
            assert "n" in loaded.rooms["room1"].exits
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_auto_layout(self):
        """Test auto-layout assigns coordinates."""
        m = MapGraph()
        
        for i in range(1, 4):
            m.add_room(RoomNode(room_id=f"room{i}", name=f"Room {i}"))
        
        m.add_edge("room1", "room2", "n")
        m.add_edge("room2", "room3", "e")
        m.set_current_room("room1")
        
        m.auto_layout()
        
        # Check coordinates are set
        assert m.rooms["room1"].x == 0
        assert m.rooms["room1"].y == 0
        assert m.rooms["room2"].x == 0
        assert m.rooms["room2"].y == -1  # North = y-1
        assert m.rooms["room3"].x == 1   # East = x+1
        assert m.rooms["room3"].y == -1
    
    def test_get_stats(self):
        """Test getting map statistics."""
        m = MapGraph()
        
        m.add_room(RoomNode(room_id="room1", name="Room 1", area="Area1"))
        m.add_room(RoomNode(room_id="room2", name="Room 2", area="Area1"))
        m.add_room(RoomNode(room_id="room3", name="Room 3", area="Area2"))
        m.add_edge("room1", "room2", "n")
        m.set_current_room("room1")
        
        stats = m.get_stats()
        
        assert stats["total_rooms"] == 3
        assert stats["total_edges"] == 1
        assert stats["current_room"] == "room1"
        assert "Area1" in stats["areas"]
        assert "Area2" in stats["areas"]
        assert stats["areas"]["Area1"] == 2


class TestMapAgent:
    """Tests for MapAgent class."""
    
    def test_create_agent(self):
        """Test creating a map agent."""
        # Create without API key (won't make LLM calls)
        agent = MapAgent(
            provider="anthropic",
            api_key="test_key",
            map_path=None,
            auto_save=False,
        )
        
        assert agent.map is not None
        assert len(agent.map.rooms) == 0
    
    def test_tool_add_room(self):
        """Test add_room tool."""
        agent = MapAgent(api_key="test", auto_save=False)
        
        result = agent.execute_tool("add_room", {
            "room_id": "room1",
            "name": "Test Room",
            "area": "Test Area",
            "description": "A test room",
        })
        
        assert result.success is True
        assert "room1" in agent.map.rooms
        assert agent.map.rooms["room1"].name == "Test Room"
    
    def test_tool_add_exit(self):
        """Test add_exit tool."""
        agent = MapAgent(api_key="test", auto_save=False)
        
        # Add two rooms
        agent.execute_tool("add_room", {"room_id": "room1", "name": "Room 1"})
        agent.execute_tool("add_room", {"room_id": "room2", "name": "Room 2"})
        
        # Add exit
        result = agent.execute_tool("add_exit", {
            "from_room_id": "room1",
            "to_room_id": "room2",
            "direction": "n",
        })
        
        assert result.success is True
        assert agent.map.rooms["room1"].exits["n"] == "room2"
    
    def test_tool_set_current_room(self):
        """Test set_current_room tool."""
        agent = MapAgent(api_key="test", auto_save=False)
        agent.execute_tool("add_room", {"room_id": "room1", "name": "Room 1"})
        
        result = agent.execute_tool("set_current_room", {"room_id": "room1"})
        
        assert result.success is True
        assert agent.map.current_room_id == "room1"
        assert agent.context.current_room_id == "room1"
    
    def test_tool_add_item(self):
        """Test add_item tool."""
        agent = MapAgent(api_key="test", auto_save=False)
        agent.execute_tool("add_room", {"room_id": "room1", "name": "Room 1"})
        
        result = agent.execute_tool("add_item", {
            "room_id": "room1",
            "name": "Sword",
            "description": "A sharp sword",
        })
        
        assert result.success is True
        assert len(agent.map.rooms["room1"].items) == 1
        assert agent.map.rooms["room1"].items[0].name == "Sword"
    
    def test_tool_add_npc(self):
        """Test add_npc tool."""
        agent = MapAgent(api_key="test", auto_save=False)
        agent.execute_tool("add_room", {"room_id": "room1", "name": "Room 1"})
        
        result = agent.execute_tool("add_npc", {
            "room_id": "room1",
            "name": "Guard",
            "hostile": True,
        })
        
        assert result.success is True
        assert len(agent.map.rooms["room1"].npcs) == 1
        assert agent.map.rooms["room1"].npcs[0].hostile is True
    
    def test_tool_add_room_tag(self):
        """Test add_room_tag tool."""
        agent = MapAgent(api_key="test", auto_save=False)
        agent.execute_tool("add_room", {"room_id": "room1", "name": "Shop"})
        
        result = agent.execute_tool("add_room_tag", {
            "room_id": "room1",
            "tag": "shop",
        })
        
        assert result.success is True
        assert "shop" in agent.map.rooms["room1"].tags
    
    def test_tool_find_route(self):
        """Test find_route tool."""
        agent = MapAgent(api_key="test", auto_save=False)
        
        # Setup rooms
        agent.execute_tool("add_room", {"room_id": "room1", "name": "Room 1"})
        agent.execute_tool("add_room", {"room_id": "room2", "name": "Room 2"})
        agent.execute_tool("add_exit", {
            "from_room_id": "room1",
            "to_room_id": "room2",
            "direction": "n",
        })
        agent.execute_tool("set_current_room", {"room_id": "room1"})
        
        result = agent.execute_tool("find_route", {"to_room_id": "room2"})
        
        assert result.success is True
        assert result.data["directions"] == ["n"]
    
    def test_tool_find_nearest_tagged(self):
        """Test find_nearest_tagged tool."""
        agent = MapAgent(api_key="test", auto_save=False)
        
        # Setup
        agent.execute_tool("add_room", {"room_id": "room1", "name": "Start"})
        agent.execute_tool("add_room", {"room_id": "room2", "name": "Shop", "tags": ["shop"]})
        agent.execute_tool("add_exit", {
            "from_room_id": "room1",
            "to_room_id": "room2",
            "direction": "e",
        })
        agent.execute_tool("set_current_room", {"room_id": "room1"})
        
        result = agent.execute_tool("find_nearest_tagged", {"tag": "shop"})
        
        assert result.success is True
        assert result.data["room_id"] == "room2"
    
    def test_update_from_gmcp(self):
        """Test updating map from GMCP data."""
        agent = MapAgent(api_key="test", auto_save=False)
        
        results = agent.update_from_gmcp(
            room_id="room1",
            room_name="Test Room",
            area="Test Area",
            environment="indoor",
            exits={"n": "room2", "s": "room3"},
            room_text="A test room description.",
        )
        
        assert len(results) > 0
        assert "room1" in agent.map.rooms
        assert agent.map.current_room_id == "room1"
        assert agent.map.rooms["room1"].exits["n"] == "room2"
        assert agent.context.current_room_id == "room1"
    
    def test_get_current_room_info(self):
        """Test getting current room info."""
        agent = MapAgent(api_key="test", auto_save=False)
        
        agent.update_from_gmcp(
            room_id="room1",
            room_name="Test Room",
            area="Test Area",
            environment="indoor",
            exits={"n": "room2"},
        )
        
        info = agent.get_current_room_info()
        
        assert info is not None
        assert info["room_id"] == "room1"
        assert info["name"] == "Test Room"
        assert info["is_current"] is True
    
    def test_get_map_data_for_visualization(self):
        """Test getting map data for frontend."""
        agent = MapAgent(api_key="test", auto_save=False)
        
        agent.update_from_gmcp(
            room_id="room1",
            room_name="Room 1",
            area="Area1",
            environment="indoor",
            exits={"n": "room2"},
        )
        
        data = agent.get_map_data_for_visualization()
        
        assert "rooms" in data
        assert "edges" in data
        assert "current_room_id" in data
        assert len(data["rooms"]) >= 1
    
    def test_map_persistence(self):
        """Test saving and loading maps."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        
        try:
            # Create agent with save path
            agent = MapAgent(
                api_key="test",
                map_path=temp_path,
                auto_save=False,
            )
            
            agent.update_from_gmcp(
                room_id="room1",
                room_name="Test Room",
                area="Test Area",
                environment="indoor",
                exits={},
            )
            
            # Save
            assert agent.save_map() is True
            
            # Create new agent and load
            agent2 = MapAgent(
                api_key="test",
                map_path=temp_path,
                auto_save=False,
            )
            
            assert agent2.load_map() is True
            assert "room1" in agent2.map.rooms
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_export_graphviz(self):
        """Test exporting map as Graphviz DOT format."""
        agent = MapAgent(api_key="test", auto_save=False)
        
        agent.update_from_gmcp(
            room_id="room1",
            room_name="Room 1",
            area="Area1",
            environment="indoor",
            exits={"n": "room2"},
        )
        
        dot = agent.export_graphviz()
        
        assert dot is not None
        assert "digraph MUDMap" in dot
        assert "room1" in dot


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
