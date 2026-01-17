#!/usr/bin/env python3
"""
Test script for GMCP attribute synchronization.
Connects to dunemud.net as guest and tests:
- Health (HP) and Command Points (SP) tracking
- Status attributes (wimpy, level, money, etc.)
- Mutating wimpy to verify local/server state synchronization
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce noise from other loggers
logging.getLogger('asyncio').setLevel(logging.WARNING)

from llmud import TelnetClient
from llmud.gmcp_handler import GMCPHandler


class GMCPAttributeTester:
    """Tests GMCP attribute synchronization by connecting to DuneMUD as a guest."""
    
    def __init__(self):
        self.telnet = TelnetClient("dunemud.net", 6789)
        self.gmcp = GMCPHandler()
        
        self.output_buffer = []
        self.gmcp_messages = []
        self.login_complete = False
        self.in_game = False
        
        # Track attribute changes
        self.vitals_history = []
        self.status_history = []
        self.rooms_detected = []
        
        # Wimpy test state
        self.initial_wimpy: Optional[int] = None
        self.target_wimpy: int = 25  # Target wimpy value for mutation test
        self.wimpy_changed = False
        self.wimpy_synced = False
        
        # Register callbacks
        self.telnet.on_text(self._on_text)
        self.telnet.on_gmcp(self._on_gmcp)
        self.gmcp.on_room_change(self._on_room_change)
        self.gmcp.on_vitals_change(self._on_vitals_change)
        self.gmcp.on_status_change(self._on_status_change)
    
    async def _on_text(self, text: str) -> None:
        """Handle text received from server."""
        self.output_buffer.append(text)
        # Print received text (limit to avoid flooding)
        for line in text.split('\n')[:5]:
            clean_line = self._strip_ansi(line).strip()
            if clean_line:
                print(f"[TEXT] {clean_line[:100]}")
        
        # Check for login/game state
        text_lower = text.lower()
        if "your choice" in text_lower and not self.login_complete:
            logger.info("Login menu detected")
        elif "you have entered" in text_lower:
            self.in_game = True
            logger.info("GAME ENTRY DETECTED!")
    
    async def _on_gmcp(self, module: str, data) -> None:
        """Handle GMCP messages."""
        self.gmcp_messages.append({
            "module": module,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        print(f"[GMCP] {module}: {data}")
        
        # Process through handler
        self.gmcp.process(module, data)
    
    def _on_room_change(self, room) -> None:
        """Handle room change event."""
        logger.info(f"ROOM CHANGE: {room.name} (ID: {room.num})")
        self.rooms_detected.append({
            "id": room.num,
            "name": room.name,
            "area": room.area,
            "environment": room.environment,
            "exits": room.exits,
            "timestamp": datetime.now().isoformat(),
        })
    
    def _on_vitals_change(self, vitals) -> None:
        """Handle vitals change event."""
        logger.info(f"VITALS CHANGE: HP={vitals.hp}/{vitals.maxhp} CP={vitals.sp}/{vitals.maxsp}")
        self.vitals_history.append({
            "hp": vitals.hp,
            "maxhp": vitals.maxhp,
            "sp": vitals.sp,
            "maxsp": vitals.maxsp,
            "hp_percent": vitals.hp_percent,
            "sp_percent": vitals.sp_percent,
            "timestamp": datetime.now().isoformat(),
        })
    
    def _on_status_change(self, status) -> None:
        """Handle status change event."""
        logger.info(
            f"STATUS CHANGE: Level={status.level} Wimpy={status.wimpy} "
            f"WimpyDir={status.wimpy_dir} Money={status.money}"
        )
        self.status_history.append({
            "level": status.level,
            "money": status.money,
            "bankmoney": status.bankmoney,
            "guild": status.guild,
            "subguild": status.subguild,
            "xp": status.xp,
            "maxxp": status.maxxp,
            "wimpy": status.wimpy,
            "wimpy_dir": status.wimpy_dir,
            "quest_points": status.quest_points,
            "kills": status.kills,
            "deaths": status.deaths,
            "explorer_rating": status.explorer_rating,
            "pk": status.pk,
            "inn": status.inn,
            "timestamp": datetime.now().isoformat(),
        })
        
        # Check if wimpy was updated to our target (for mutation test)
        if status.wimpy == self.target_wimpy and self.wimpy_changed:
            self.wimpy_synced = True
            logger.info(f"WIMPY SYNC CONFIRMED: Server reports wimpy={status.wimpy}")
    
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
    
    async def test_wimpy_mutation(self) -> dict:
        """
        Test wimpy attribute mutation and sync.
        
        This tests that:
        1. We can read the current wimpy value from GMCP
        2. We can send a command to change wimpy
        3. The server reports the new wimpy value back via GMCP
        """
        results = {
            "initial_wimpy": None,
            "initial_wimpy_dir": None,
            "target_wimpy": self.target_wimpy,
            "command_sent": False,
            "sync_confirmed": False,
            "final_wimpy": None,
            "final_wimpy_dir": None,
        }
        
        # Record initial wimpy value using helper method
        self.initial_wimpy, initial_dir = self.gmcp.get_wimpy()
        results["initial_wimpy"] = self.initial_wimpy
        results["initial_wimpy_dir"] = initial_dir
        logger.info(f"Initial wimpy: {self.initial_wimpy} (direction: {initial_dir})")
        
        # Choose a different target if initial is already our target
        if self.initial_wimpy == self.target_wimpy:
            self.target_wimpy = 30 if self.initial_wimpy != 30 else 20
            results["target_wimpy"] = self.target_wimpy
        
        # Clear received modules to track fresh sync
        self.gmcp.clear_received_modules()
        
        # Generate and send wimpy command using helper method
        wimpy_cmd = GMCPHandler.cmd_set_wimpy(self.target_wimpy)
        logger.info(f"Setting wimpy to {self.target_wimpy} with command: {wimpy_cmd}")
        self.wimpy_changed = True
        await self.send_and_wait(wimpy_cmd, 3.0)
        results["command_sent"] = True
        
        # Wait for GMCP update
        await asyncio.sleep(1.0)
        for _ in range(10):
            await self.telnet.receive()
            await asyncio.sleep(0.2)
        
        # Check if sync was confirmed using helper methods
        results["sync_confirmed"] = self.wimpy_synced
        final_wimpy, final_dir = self.gmcp.get_wimpy()
        results["final_wimpy"] = final_wimpy
        results["final_wimpy_dir"] = final_dir
        
        # Check if Char.Status was received after mutation
        status_received_after = self.gmcp.has_status()
        logger.info(f"Char.Status received after mutation: {status_received_after}")
        
        # Restore original wimpy
        if self.initial_wimpy is not None and self.initial_wimpy != self.target_wimpy:
            restore_cmd = GMCPHandler.cmd_set_wimpy(self.initial_wimpy)
            logger.info(f"Restoring wimpy to {self.initial_wimpy} with command: {restore_cmd}")
            await self.send_and_wait(restore_cmd, 2.0)
        
        return results

    async def test_aim_mutation(self) -> dict:
        """
        Test aim attribute mutation and sync.
        
        This tests that:
        1. We can read the current aim value from GMCP
        2. We can send a command to change aim
        3. The server reports the new aim value back via GMCP
        """
        results = {
            "initial_aim": None,
            "target_aim": "head",
            "command_sent": False,
            "sync_received": False,
            "final_aim": None,
        }
        
        # Record initial aim value using helper method
        initial_aim = self.gmcp.get_aim()
        results["initial_aim"] = initial_aim
        logger.info(f"Initial aim: {initial_aim}")
        
        # Choose a different target aim
        if initial_aim == "head":
            results["target_aim"] = "torso"
        
        # Clear received modules to track fresh sync
        self.gmcp.clear_received_modules()
        
        # Generate and send aim command
        aim_cmd = GMCPHandler.cmd_set_aim(results["target_aim"])
        logger.info(f"Setting aim to {results['target_aim']} with command: {aim_cmd}")
        await self.send_and_wait(aim_cmd, 2.0)
        results["command_sent"] = True
        
        # Wait for GMCP update
        await asyncio.sleep(1.0)
        for _ in range(5):
            await self.telnet.receive()
            await asyncio.sleep(0.2)
        
        # Check final aim
        final_aim = self.gmcp.get_aim()
        results["final_aim"] = final_aim
        results["sync_received"] = self.gmcp.has_status()
        
        # Clear aim (restore to no target)
        clear_cmd = GMCPHandler.cmd_clear_aim()
        logger.info(f"Clearing aim with command: {clear_cmd}")
        await self.send_and_wait(clear_cmd, 1.0)
        
        return results
    
    async def run_test(self) -> dict:
        """Run the GMCP attribute synchronization test."""
        results = {
            "connected": False,
            "gmcp_enabled": False,
            "logged_in": False,
            "vitals_received": False,
            "status_received": False,
            "wimpy_mutation_test": {},
            "aim_mutation_test": {},
            "attribute_summary": {},
            "gmcp_messages_count": 0,
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
                results["issues"].append("GMCP not enabled - attribute sync won't work")
            
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
            
            results["logged_in"] = True
            logger.info("Attempting to gather character attributes...")
            
            # Look around and check score to trigger GMCP updates
            await self.send_and_wait("look", 2)
            await self.send_and_wait("score", 2)
            await self.send_and_wait("wimpy", 2)  # Check current wimpy
            
            # Verify vitals were received
            results["vitals_received"] = len(self.vitals_history) > 0
            if not results["vitals_received"]:
                results["issues"].append("No vitals (HP/CP) received via GMCP Char.Vitals")
            
            # Verify status was received
            results["status_received"] = len(self.status_history) > 0
            if not results["status_received"]:
                results["issues"].append("No status (wimpy, level, etc.) received via GMCP Char.Status")
            
            # Run wimpy mutation test
            logger.info("\n" + "="*60)
            logger.info("RUNNING WIMPY MUTATION TEST")
            logger.info("="*60)
            results["wimpy_mutation_test"] = await self.test_wimpy_mutation()
            
            # Run aim mutation test
            logger.info("\n" + "="*60)
            logger.info("RUNNING AIM MUTATION TEST")
            logger.info("="*60)
            results["aim_mutation_test"] = await self.test_aim_mutation()
            
            if not results["wimpy_mutation_test"]["sync_confirmed"]:
                results["issues"].append(
                    f"Wimpy sync failed: sent {results['wimpy_mutation_test']['target_wimpy']}, "
                    f"got {results['wimpy_mutation_test']['final_wimpy']}"
                )
            
            # Collect final results
            results["gmcp_messages_count"] = len(self.gmcp_messages)
            results["attribute_summary"] = self.gmcp.get_state_summary()
            
            # Log detailed results
            logger.info("\n" + "="*60)
            logger.info("TEST RESULTS")
            logger.info("="*60)
            logger.info(f"Connected: {results['connected']}")
            logger.info(f"GMCP Enabled: {results['gmcp_enabled']}")
            logger.info(f"GMCP Messages Received: {results['gmcp_messages_count']}")
            logger.info(f"Vitals Updates Received: {len(self.vitals_history)}")
            logger.info(f"Status Updates Received: {len(self.status_history)}")
            
            if self.vitals_history:
                latest_vitals = self.vitals_history[-1]
                logger.info(f"\nLatest Vitals:")
                logger.info(f"  HP: {latest_vitals['hp']}/{latest_vitals['maxhp']} ({latest_vitals['hp_percent']:.1f}%)")
                logger.info(f"  CP: {latest_vitals['sp']}/{latest_vitals['maxsp']} ({latest_vitals['sp_percent']:.1f}%)")
            
            if self.status_history:
                latest_status = self.status_history[-1]
                logger.info(f"\nLatest Status:")
                logger.info(f"  Level: {latest_status['level']}")
                logger.info(f"  Wimpy: {latest_status['wimpy']} (direction: {latest_status['wimpy_dir']})")
                logger.info(f"  Money: {latest_status['money']} (bank: {latest_status['bankmoney']})")
                logger.info(f"  Guild: {latest_status['guild']} / {latest_status['subguild']}")
                logger.info(f"  XP: {latest_status['xp']}/{latest_status['maxxp']}")
                logger.info(f"  Explorer Rating: {latest_status['explorer_rating']}")
            
            logger.info(f"\nWimpy Mutation Test:")
            logger.info(f"  Initial: {results['wimpy_mutation_test'].get('initial_wimpy')}")
            logger.info(f"  Target: {results['wimpy_mutation_test'].get('target_wimpy')}")
            logger.info(f"  Final: {results['wimpy_mutation_test'].get('final_wimpy')}")
            logger.info(f"  Sync Confirmed: {results['wimpy_mutation_test'].get('sync_confirmed')}")
            
            logger.info(f"\nAim Mutation Test:")
            logger.info(f"  Initial: {results['aim_mutation_test'].get('initial_aim')}")
            logger.info(f"  Target: {results['aim_mutation_test'].get('target_aim')}")
            logger.info(f"  Final: {results['aim_mutation_test'].get('final_aim')}")
            logger.info(f"  Sync Received: {results['aim_mutation_test'].get('sync_received')}")
            
            # Print all GMCP message types received
            gmcp_types = set(m["module"] for m in self.gmcp_messages)
            logger.info(f"\nGMCP Message Types Received: {gmcp_types}")
            
            if results['issues']:
                logger.warning("\nISSUES FOUND:")
                for issue in results['issues']:
                    logger.warning(f"  - {issue}")
            
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
    tester = GMCPAttributeTester()
    results = await tester.run_test()
    
    print("\n" + "="*60)
    print("FINAL TEST RESULTS - GMCP ATTRIBUTE SYNCHRONIZATION")
    print("="*60)
    print(f"Connected: {results['connected']}")
    print(f"GMCP Enabled: {results['gmcp_enabled']}")
    print(f"Vitals Received: {results['vitals_received']}")
    print(f"Status Received: {results['status_received']}")
    print(f"GMCP Messages Count: {results['gmcp_messages_count']}")
    
    print("\nWimpy Mutation Test:")
    wmt = results.get('wimpy_mutation_test', {})
    print(f"  Initial Wimpy: {wmt.get('initial_wimpy')}")
    print(f"  Target Wimpy: {wmt.get('target_wimpy')}")
    print(f"  Final Wimpy: {wmt.get('final_wimpy')}")
    print(f"  Sync Confirmed: {wmt.get('sync_confirmed')}")
    
    print("\nAim Mutation Test:")
    amt = results.get('aim_mutation_test', {})
    print(f"  Initial Aim: {amt.get('initial_aim')}")
    print(f"  Target Aim: {amt.get('target_aim')}")
    print(f"  Final Aim: {amt.get('final_aim')}")
    print(f"  Sync Received: {amt.get('sync_received')}")
    
    if results.get('attribute_summary'):
        print("\nAttribute Summary:")
        summary = results['attribute_summary']
        if 'character' in summary:
            char = summary['character']
            print(f"  Character: {char.get('name', 'Unknown')}")
            print(f"  HP: {char.get('hp', '?')}")
            print(f"  CP: {char.get('cp', '?')}")
            print(f"  Wimpy: {char.get('wimpy', '?')}")
    
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
