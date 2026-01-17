#!/usr/bin/env python3
"""
Test script for the MUD mapper functionality.
Connects to dunemud.net as guest and tests room detection and mapping.
"""

import asyncio
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce noise from other loggers
logging.getLogger('asyncio').setLevel(logging.WARNING)

from llmud import TelnetClient, GMCPHandler, MapAgent

class MapperTester:
    """Tests the mapper functionality by connecting to DuneMUD as a guest."""
    
    def __init__(self):
        self.telnet = TelnetClient("dunemud.net", 6789)
        self.gmcp = GMCPHandler()
        self.map_agent = MapAgent(
            provider="anthropic",
            api_key=None,  # Not using LLM analysis for this test
            map_path="/workspace/test_map.json",
            auto_save=True,
        )
        
        self.output_buffer = []
        self.gmcp_messages = []
        self.rooms_detected = []
        self.login_complete = False
        self.in_game = False
        
        # Register callbacks
        self.telnet.on_text(self._on_text)
        self.telnet.on_gmcp(self._on_gmcp)
        self.gmcp.on_room_change(self._on_room_change)
        self.gmcp.on_vitals_change(self._on_vitals_change)
    
    async def _on_text(self, text: str) -> None:
        """Handle text received from server."""
        self.output_buffer.append(text)
        # Print received text (limit to avoid flooding)
        for line in text.split('\n')[:5]:
            clean_line = self._strip_ansi(line).strip()
            if clean_line:
                print(f"[TEXT] {clean_line[:100]}")
        
        # Check for login prompts
        text_lower = text.lower()
        if "your choice" in text_lower and not self.login_complete:
            logger.info("Login menu detected")
        elif "press enter" in text_lower or "continue" in text_lower:
            pass
        elif "you have entered" in text_lower:
            self.in_game = True
            logger.info("GAME ENTRY DETECTED!")
    
    async def _on_gmcp(self, module: str, data) -> None:
        """Handle GMCP messages."""
        self.gmcp_messages.append((module, data))
        print(f"[GMCP] {module}: {data}")
        
        # Process through handler
        self.gmcp.process(module, data)
    
    def _on_room_change(self, room) -> None:
        """Handle room change event."""
        logger.info(f"ROOM CHANGE DETECTED: {room.name} (ID: {room.num})")
        self.rooms_detected.append({
            "id": room.num,
            "name": room.name,
            "area": room.area,
            "environment": room.environment,
            "exits": room.exits,
            "timestamp": datetime.now().isoformat(),
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
                logger.info(f"  Map update: {r.message}")
    
    def _on_vitals_change(self, vitals) -> None:
        """Handle vitals change event."""
        logger.info(f"VITALS: HP={vitals.hp}/{vitals.maxhp} CP={vitals.sp}/{vitals.maxsp}")
    
    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    async def send_and_wait(self, command: str, wait_time: float = 2.0) -> None:
        """Send a command and wait for response."""
        logger.info(f"SENDING: {command}")
        await self.telnet.send(command)
        
        # Receive data for wait_time seconds
        end_time = asyncio.get_event_loop().time() + wait_time
        while asyncio.get_event_loop().time() < end_time:
            try:
                await self.telnet.receive()
            except Exception as e:
                logger.error(f"Receive error: {e}")
                break
            await asyncio.sleep(0.1)
    
    async def run_test(self) -> dict:
        """Run the mapper test."""
        results = {
            "connected": False,
            "gmcp_enabled": False,
            "logged_in": False,
            "rooms_detected": 0,
            "map_stats": {},
            "issues": [],
        }
        
        try:
            # Connect
            logger.info("Connecting to dunemud.net:6789...")
            if not await self.telnet.connect():
                results["issues"].append("Failed to connect to server")
                return results
            
            results["connected"] = True
            logger.info("Connected!")
            
            # Wait for initial data and GMCP negotiation
            logger.info("Waiting for GMCP negotiation...")
            await asyncio.sleep(2)
            
            # Receive initial data
            for _ in range(20):
                await self.telnet.receive()
                await asyncio.sleep(0.2)
            
            results["gmcp_enabled"] = self.telnet.gmcp_enabled
            logger.info(f"GMCP enabled: {self.telnet.gmcp_enabled}")
            
            if not self.telnet.gmcp_enabled:
                results["issues"].append("GMCP not enabled - room detection won't work via GMCP")
            
            # Login as guest
            logger.info("Logging in as guest...")
            await self.send_and_wait("guest", 2)
            
            # Handle guest login prompts
            await self.send_and_wait("", 1)  # Press enter to continue
            await self.send_and_wait("", 1)  # Press enter again if needed
            await self.send_and_wait("1", 2)  # Choose option 1 if there's a menu
            await self.send_and_wait("", 1)  
            
            # Wait for game entry
            await asyncio.sleep(2)
            for _ in range(10):
                await self.telnet.receive()
                await asyncio.sleep(0.2)
            
            results["logged_in"] = True  # Assume we logged in
            logger.info("Attempting navigation commands...")
            
            # Look around
            await self.send_and_wait("look", 2)
            
            # Try some movement commands
            movement_commands = ["n", "s", "e", "w", "look"]
            for cmd in movement_commands:
                await self.send_and_wait(cmd, 1.5)
            
            # Check results
            results["rooms_detected"] = len(self.rooms_detected)
            results["gmcp_messages_count"] = len(self.gmcp_messages)
            results["map_stats"] = self.map_agent.get_map_stats()
            
            # Analyze issues
            if len(self.rooms_detected) == 0:
                results["issues"].append("No rooms detected via GMCP Room.Info")
            
            room_info_messages = [m for m in self.gmcp_messages if m[0] == "Room.Info"]
            if len(room_info_messages) == 0:
                results["issues"].append("No Room.Info GMCP messages received")
            
            # Log detailed results
            logger.info("\n" + "="*60)
            logger.info("TEST RESULTS")
            logger.info("="*60)
            logger.info(f"Connected: {results['connected']}")
            logger.info(f"GMCP Enabled: {results['gmcp_enabled']}")
            logger.info(f"GMCP Messages Received: {len(self.gmcp_messages)}")
            logger.info(f"Rooms Detected: {len(self.rooms_detected)}")
            
            if self.rooms_detected:
                logger.info("\nDetected Rooms:")
                for room in self.rooms_detected:
                    logger.info(f"  - {room['name']} (ID: {room['id']}, Area: {room['area']})")
                    logger.info(f"    Exits: {room['exits']}")
            
            logger.info(f"\nMap Stats: {results['map_stats']}")
            
            if results['issues']:
                logger.warning("\nISSUES FOUND:")
                for issue in results['issues']:
                    logger.warning(f"  - {issue}")
            
            # Print all GMCP message types received
            gmcp_types = set(m[0] for m in self.gmcp_messages)
            logger.info(f"\nGMCP Message Types Received: {gmcp_types}")
            
        except Exception as e:
            logger.error(f"Test error: {e}")
            results["issues"].append(f"Exception: {str(e)}")
            import traceback
            traceback.print_exc()
        
        finally:
            logger.info("Disconnecting...")
            await self.telnet.disconnect()
        
        return results


async def main():
    """Main entry point."""
    tester = MapperTester()
    results = await tester.run_test()
    
    print("\n" + "="*60)
    print("FINAL TEST RESULTS")
    print("="*60)
    print(f"Connected: {results['connected']}")
    print(f"GMCP Enabled: {results['gmcp_enabled']}")
    print(f"Rooms Detected: {results['rooms_detected']}")
    print(f"Map Stats: {results['map_stats']}")
    
    if results['issues']:
        print("\nISSUES:")
        for issue in results['issues']:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print("\nNo issues found!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
