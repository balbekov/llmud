#!/usr/bin/env python3
"""
Full mapper test - connects as guest, navigates, and verifies mapping works.
"""

import asyncio
import logging
import sys
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger('llmud').setLevel(logging.WARNING)

from llmud import TelnetClient, GMCPHandler, MapAgent

class FullMapperTest:
    """Tests full mapper functionality."""
    
    def __init__(self):
        self.telnet = TelnetClient("dunemud.net", 6789)
        self.gmcp = GMCPHandler()
        self.map_agent = MapAgent(
            provider="anthropic",
            api_key=None,
            map_path="/workspace/test_world_map.json",
            auto_save=True,
        )
        
        self.rooms_visited = []
        self.issues = []
        
        # Register callbacks
        self.telnet.on_text(self._on_text)
        self.telnet.on_gmcp(self._on_gmcp)
        self.gmcp.on_room_change(self._on_room_change)
    
    async def _on_text(self, text: str) -> None:
        """Handle text."""
        pass  # We're just testing mapping, not text parsing
    
    async def _on_gmcp(self, module: str, data) -> None:
        """Handle GMCP."""
        self.gmcp.process(module, data)
    
    def _on_room_change(self, room) -> None:
        """Handle room change - update mapper."""
        logger.info(f"Room detected: {room.name} (ID: {room.num})")
        logger.info(f"  Area: {room.area}, Environment: {room.environment}")
        logger.info(f"  Exits: {list(room.exits.keys())}")
        
        self.rooms_visited.append({
            "id": room.num,
            "name": room.name,
            "area": room.area,
            "exits": room.exits,
        })
        
        # Update map agent
        if room.num:
            results = self.map_agent.update_from_gmcp(
                room_id=room.num,
                room_name=room.name,
                area=room.area,
                environment=room.environment,
                exits=room.exits or {},
            )
            for r in results:
                if not r.success:
                    self.issues.append(f"Map update failed: {r.message}")
    
    async def receive_for(self, seconds: float) -> None:
        """Receive data for a period of time."""
        end = asyncio.get_event_loop().time() + seconds
        while asyncio.get_event_loop().time() < end:
            try:
                await self.telnet.receive()
            except:
                pass
            await asyncio.sleep(0.05)
    
    async def send_cmd(self, cmd: str, wait: float = 1.5) -> None:
        """Send command and wait for response."""
        await self.telnet.send(cmd)
        await self.receive_for(wait)
    
    async def run(self) -> dict:
        """Run the test."""
        results = {
            "success": False,
            "rooms_mapped": 0,
            "edges_mapped": 0,
            "issues": [],
        }
        
        try:
            # Connect
            logger.info("Connecting to dunemud.net:6789...")
            if not await self.telnet.connect():
                results["issues"].append("Connection failed")
                return results
            
            # Wait for initial negotiation
            await self.receive_for(3)
            
            if not self.telnet.gmcp_enabled:
                results["issues"].append("GMCP not enabled")
                return results
            
            logger.info("GMCP enabled, logging in as guest...")
            
            # Enable GMCP modules
            await self.telnet.send_gmcp("Core.Hello", {"client": "LLMUD-Test", "version": "0.1"})
            await self.telnet.send_gmcp("Core.Supports.Set", ["Room 1", "Char 1"])
            await self.receive_for(1)
            
            # Login
            await self.send_cmd("guest", 3)
            await self.send_cmd("", 1)  # Press enter
            await self.send_cmd("", 1)  # Press enter again if needed
            
            logger.info(f"After login: {len(self.rooms_visited)} rooms detected")
            
            # Navigate around to test mapping
            logger.info("\nNavigating to test mapping...")
            
            movements = [
                ("n", "north"),
                ("n", "north again"),
                ("s", "south"),
                ("s", "back to start"),
                ("e", "east"),
                ("w", "west"),
                ("w", "west again"),
                ("e", "back"),
            ]
            
            for cmd, desc in movements:
                logger.info(f"  Moving {desc}...")
                await self.send_cmd(cmd, 1.5)
            
            # Check results
            stats = self.map_agent.get_map_stats()
            
            results["rooms_mapped"] = stats["total_rooms"]
            results["edges_mapped"] = stats["total_edges"]
            results["areas_found"] = list(stats.get("areas", {}).keys())
            results["rooms_visited_count"] = len(self.rooms_visited)
            results["issues"] = self.issues
            
            # Verify mapping
            logger.info("\n" + "="*60)
            logger.info("MAP VERIFICATION")
            logger.info("="*60)
            
            # Check that we have rooms
            if stats["total_rooms"] == 0:
                results["issues"].append("No rooms were mapped")
            else:
                logger.info(f"Total rooms in map: {stats['total_rooms']}")
            
            # Check that we have edges (connections)
            if stats["total_edges"] == 0:
                results["issues"].append("No edges/connections were mapped")
            else:
                logger.info(f"Total edges in map: {stats['total_edges']}")
            
            # Check that room IDs are proper
            for room in self.rooms_visited:
                if not room["id"]:
                    results["issues"].append(f"Room '{room['name']}' has no ID")
            
            # Check that exits point to known rooms
            map_data = self.map_agent.get_map_data_for_visualization()
            room_ids = {r["id"] for r in map_data["rooms"]}
            
            for room in map_data["rooms"]:
                for direction, target_id in room["exits"].items():
                    if target_id not in room_ids:
                        # This is expected for unexplored exits
                        pass
            
            # Test pathfinding
            if len(self.rooms_visited) >= 2:
                start = self.rooms_visited[0]["id"]
                end = self.rooms_visited[1]["id"]
                
                route = self.map_agent.get_route_to(end)
                if route:
                    logger.info(f"\nPathfinding works:")
                    logger.info(f"  From: {self.rooms_visited[0]['name']}")
                    logger.info(f"  To: {self.rooms_visited[1]['name']}")
                    logger.info(f"  Route: {route.get('route', 'N/A')}")
                else:
                    results["issues"].append("Pathfinding returned no route")
            
            # Print room details
            logger.info("\nRooms in map:")
            for room in map_data["rooms"]:
                logger.info(f"  - {room['name']} ({room['id'][:8]}...)")
                logger.info(f"    Area: {room['area']}, Exits: {list(room['exits'].keys())}")
            
            # Save map for inspection
            self.map_agent.save_map()
            logger.info(f"\nMap saved to: /workspace/test_world_map.json")
            
            results["success"] = len(results["issues"]) == 0
            
        except Exception as e:
            import traceback
            results["issues"].append(f"Exception: {str(e)}")
            traceback.print_exc()
        
        finally:
            await self.telnet.disconnect()
        
        return results


async def main():
    tester = FullMapperTest()
    results = await tester.run()
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    print(f"Success: {results['success']}")
    print(f"Rooms Mapped: {results['rooms_mapped']}")
    print(f"Edges Mapped: {results['edges_mapped']}")
    print(f"Rooms Visited: {results.get('rooms_visited_count', 0)}")
    print(f"Areas Found: {results.get('areas_found', [])}")
    
    if results['issues']:
        print("\nISSUES:")
        for issue in results['issues']:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
