#!/usr/bin/env python3
"""
Unit test for map_graph bug fixes:
1. Direction normalization (no duplicate exits)
2. No duplicate edges
3. Cycles work correctly
"""

import sys
sys.path.insert(0, '/workspace/mud_client')

from llmud.map_graph import MapGraph, RoomNode, Direction

def test_direction_normalization():
    """Test that directions are normalized to short form."""
    print("Test 1: Direction Normalization")
    print("-" * 40)
    
    graph = MapGraph(name="test")
    
    # Add a room
    room1 = RoomNode(room_id="room1", name="Starting Room", area="test")
    graph.add_room(room1)
    
    # Add exits with both long and short forms
    room1.add_exit("north", "room2")
    room1.add_exit("n", "room2")  # Should not create duplicate
    room1.add_exit("south", "room3")
    room1.add_exit("northeast", "room4")
    room1.add_exit("ne", "room4")  # Should not create duplicate
    
    # Check that exits are normalized
    print(f"  Room exits: {room1.exits}")
    
    assert "north" not in room1.exits, "Long form 'north' should not exist"
    assert "n" in room1.exits, "Short form 'n' should exist"
    assert "south" not in room1.exits, "Long form 'south' should not exist"
    assert "s" in room1.exits, "Short form 's' should exist"
    assert "northeast" not in room1.exits, "Long form 'northeast' should not exist"
    assert "ne" in room1.exits, "Short form 'ne' should exist"
    
    # Should only have 3 exits, not 5
    assert len(room1.exits) == 3, f"Expected 3 exits, got {len(room1.exits)}"
    
    print("  ✓ All directions normalized correctly!")
    print()
    return True

def test_no_duplicate_edges():
    """Test that duplicate edges are not created."""
    print("Test 2: No Duplicate Edges")
    print("-" * 40)
    
    graph = MapGraph(name="test")
    
    # Add rooms
    room1 = RoomNode(room_id="room1", name="Room 1")
    room2 = RoomNode(room_id="room2", name="Room 2")
    graph.add_room(room1)
    graph.add_room(room2)
    
    # Add same edge multiple times with different direction forms
    graph.add_edge("room1", "room2", "north")
    graph.add_edge("room1", "room2", "n")  # Same edge, short form
    graph.add_edge("room1", "room2", "north")  # Duplicate
    graph.add_edge("room1", "room2", "n")  # Duplicate
    
    print(f"  Edge count: {len(graph.edges)}")
    print(f"  Edges: {[(e.from_room, e.to_room, e.direction) for e in graph.edges]}")
    
    # Should only have 1 edge (plus possibly the reverse)
    unique_edges = set((e.from_room, e.to_room, e.direction) for e in graph.edges)
    assert len(unique_edges) == len(graph.edges), f"Found duplicate edges!"
    assert len(graph.edges) == 1, f"Expected 1 edge, got {len(graph.edges)}"
    
    print("  ✓ No duplicate edges created!")
    print()
    return True

def test_cycles_work():
    """Test that graph cycles work correctly."""
    print("Test 3: Graph Cycles")
    print("-" * 40)
    
    graph = MapGraph(name="test")
    
    # Create a cycle: room1 -> room2 -> room3 -> room4 -> room1
    rooms = [
        RoomNode(room_id="room1", name="Room 1"),
        RoomNode(room_id="room2", name="Room 2"),
        RoomNode(room_id="room3", name="Room 3"),
        RoomNode(room_id="room4", name="Room 4"),
    ]
    
    for room in rooms:
        graph.add_room(room)
    
    # Create cycle
    graph.add_edge("room1", "room2", "n")
    graph.add_edge("room2", "room3", "e")
    graph.add_edge("room3", "room4", "s")
    graph.add_edge("room4", "room1", "w")  # Completes the cycle
    
    print(f"  Rooms: {[r.name for r in rooms]}")
    print(f"  Edges: {len(graph.edges)}")
    
    # Test pathfinding around the cycle
    path_1_to_3 = graph.find_path("room1", "room3")
    print(f"  Path room1 -> room3: {path_1_to_3}")
    assert path_1_to_3 is not None, "Should find path from room1 to room3"
    assert path_1_to_3 == ["n", "e"], f"Expected ['n', 'e'], got {path_1_to_3}"
    
    path_3_to_1 = graph.find_path("room3", "room1")
    print(f"  Path room3 -> room1: {path_3_to_1}")
    assert path_3_to_1 is not None, "Should find path from room3 to room1"
    # Can go either s->w or back n->w depending on bidirectional
    
    # Verify speedwalk generation
    speedwalk = graph.get_route_commands("room1", "room4")
    print(f"  Speedwalk room1 -> room4: {speedwalk}")
    assert speedwalk is not None, "Should generate speedwalk command"
    
    print("  ✓ Cycles work correctly!")
    print()
    return True

def test_revisiting_rooms():
    """Test that revisiting rooms doesn't create duplicates."""
    print("Test 4: Revisiting Rooms (Simulating Exploration)")
    print("-" * 40)
    
    graph = MapGraph(name="test")
    
    # Simulate GMCP updates like in real gameplay
    def simulate_room_enter(room_id, room_name, exits_dict):
        """Simulate entering a room and receiving GMCP data."""
        room = graph.get_or_create_room(room_id, room_name)
        graph.set_current_room(room_id)
        
        for direction, target_id in exits_dict.items():
            graph.add_edge(room_id, target_id, direction)
    
    # First visit to room A
    simulate_room_enter("A", "Room A", {"n": "B", "e": "C"})
    
    # Move to room B
    simulate_room_enter("B", "Room B", {"s": "A", "n": "D"})
    
    # Move to room D
    simulate_room_enter("D", "Room D", {"s": "B"})
    
    # Move back to B (revisit)
    simulate_room_enter("B", "Room B", {"s": "A", "n": "D"})
    
    # Move back to A (revisit)
    simulate_room_enter("A", "Room A", {"n": "B", "e": "C"})
    
    # Move to C
    simulate_room_enter("C", "Room C", {"w": "A"})
    
    # Move back to A (revisit again)
    simulate_room_enter("A", "Room A", {"n": "B", "e": "C"})
    
    print(f"  Rooms in graph: {len(graph.rooms)}")
    print(f"  Edges in graph: {len(graph.edges)}")
    
    # Check for duplicates
    room_a = graph.get_room("A")
    print(f"  Room A exits: {room_a.exits}")
    print(f"  Room A visit count: {room_a.visit_count}")
    
    # Should have exactly 2 exits, not more
    assert len(room_a.exits) == 2, f"Room A should have 2 exits, got {len(room_a.exits)}"
    
    # Check no duplicate edges
    edge_keys = [(e.from_room, e.to_room, e.direction) for e in graph.edges]
    unique_keys = set(edge_keys)
    print(f"  Unique edges: {len(unique_keys)}")
    assert len(edge_keys) == len(unique_keys), "Found duplicate edges!"
    
    # Verify pathfinding still works after revisits
    path = graph.find_path("D", "C")
    print(f"  Path D -> C: {path}")
    assert path is not None, "Should find path through cycle"
    
    print("  ✓ Revisiting rooms works correctly!")
    print()
    return True

def main():
    print("=" * 60)
    print("MAP GRAPH BUG FIX VERIFICATION TESTS")
    print("=" * 60)
    print()
    
    all_passed = True
    
    all_passed &= test_direction_normalization()
    all_passed &= test_no_duplicate_edges()
    all_passed &= test_cycles_work()
    all_passed &= test_revisiting_rooms()
    
    print("=" * 60)
    if all_passed:
        print("ALL TESTS PASSED! ✓")
        print("=" * 60)
        sys.exit(0)
    else:
        print("SOME TESTS FAILED!")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
