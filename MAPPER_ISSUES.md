# Mapper Issues Found During Testing

**Date**: 2026-01-17  
**Test Environment**: dunemud.net:6789 (guest login)

## Summary

The mapper's core functionality works:
- ✅ Connection to DuneMUD works
- ✅ GMCP negotiation succeeds
- ✅ Room.Info messages are received
- ✅ Rooms are detected and added to the map
- ✅ Exits are recorded
- ✅ Pathfinding works

However, several issues were identified:

---

## Issue 1: Duplicate Exits in Room Data

**Severity**: Medium  
**Location**: `mud_client/llmud/map_agent.py` and `map_graph.py`

**Description**: Rooms have duplicate exits with both abbreviated and full direction names.

**Example**:
```json
"exits": {
  "north": "d71af6ab78c572da8d571296a2dc0493",
  "n": "d71af6ab78c572da8d571296a2dc0493",
  "west": "0886a1743230b88efd2102ba0ceb6641", 
  "w": "0886a1743230b88efd2102ba0ceb6641"
}
```

**Root Cause**: 
When `record_movement(direction, new_room_id)` is called in `mud_session.py`, it uses the abbreviated direction (e.g., 'n'), but when `update_from_gmcp()` is called, it receives the full direction from GMCP (e.g., 'north'). Both get added to the room's exits.

**Fix Needed**: Normalize directions to a canonical form (either always short or always long) before adding to exits.

---

## Issue 2: Duplicate Edges in Edge List

**Severity**: Medium  
**Location**: `mud_client/llmud/map_graph.py` `add_edge()` method

**Description**: The edges list contains duplicate entries for the same connection.

**Example**: The edge from room `af3c8e77...` to `0886a174...` with direction "west" appears 4 times in the edges list.

**Root Cause**: The `add_edge()` method appends to the edge list without checking if an identical edge already exists. Every time `update_from_gmcp()` is called for a room, it re-adds all edges.

**Fix Needed**: Check for existing edges before adding, or use a set/dict structure instead of a list.

---

## Issue 3: First Room.Info Message Sometimes Missed

**Severity**: Low  
**Location**: `mud_client/llmud/telnet_client.py` and session handling

**Description**: The login room "Caladan Astro Port" (ID: `52164e3cd745c1040e279394bff1f44d`) was detected in earlier debug tests but appears only as a placeholder in the full mapper test.

**Root Cause**: Timing-dependent - the first Room.Info message sent during login may be processed before the room change callback is fully registered, or before the GMCP handler is ready.

**Fix Needed**: Ensure GMCP handlers are registered before any data can arrive, or queue early GMCP messages for reprocessing.

---

## Issue 4: Placeholder Rooms Have Generic Names

**Severity**: Low  
**Location**: `mud_client/llmud/map_graph.py` `get_or_create_room()` method

**Description**: When creating a placeholder room for an unvisited exit destination, the room gets a generic name like "Room 52164e3cd745c1040e279394bff1f44d".

**Current Behavior**: This is expected since we don't know the room name until we visit it.

**Potential Improvement**: Could mark these rooms as "unexplored" with a flag, or use a naming convention like "Unexplored (via north from X)".

---

## Issue 5: Auto-Layout Not Persisted

**Severity**: Low  
**Location**: `mud_client/llmud/map_agent.py` `get_map_data_for_visualization()`

**Description**: Room coordinates (x, y, z) are all 0 in the saved JSON even though auto_layout is called.

**Root Cause**: `auto_layout()` is called in `get_map_data_for_visualization()` which happens AFTER saving. The layout should be persisted or recalculated on load.

**Fix Needed**: Call `auto_layout()` before saving, or save layout data separately.

---

## Recommendations

### Priority 1 (Should Fix)
1. **Normalize direction names** - Create a utility function that converts all directions to a canonical form
2. **Prevent duplicate edges** - Add a check in `add_edge()` or change to a set-based structure

### Priority 2 (Nice to Have)
3. **Ensure GMCP ready before login** - Add a small delay or state check
4. **Persist auto-layout** - Save coordinates after calculating layout

### Priority 3 (Future Enhancement)
5. **Mark unexplored rooms** - Add an `explored` flag to RoomNode
6. **Room descriptions from text** - Parse room descriptions from text output to fill in missing GMCP data

---

## Test Files Created

- `/workspace/test_mapper.py` - Basic connection test
- `/workspace/test_mapper_v2.py` - GMCP debug test  
- `/workspace/test_mapper_full.py` - Full mapper integration test
- `/workspace/test_world_map.json` - Sample map output

All tests can be run with: `python3 /workspace/test_mapper_full.py`
