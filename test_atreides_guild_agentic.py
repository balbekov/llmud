#!/usr/bin/env python3
"""
Agentic AI Test - Atreides Guild

This test connects to DuneMUD with a real user account and uses an LLM agent
to autonomously:
1. Navigate to the Atreides guild (6 north from starting position)
2. Join the Atreides guild
3. Get a weapon from the guild armory

Uses OpenAI gpt-5.1-thinking model for decision making.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger('asyncio').setLevel(logging.WARNING)

from llmud import TelnetClient
from llmud.gmcp_handler import GMCPHandler
from llmud.llm_agent import LLMAgent, LLMResponse


class AtreidesGuildAgentTest:
    """
    Agentic test that uses LLM to navigate to Atreides guild, join, and get a weapon.
    """
    
    # Credentials
    USERNAME = "ditherer"
    PASSWORD = "dither2025"
    
    # LLM Configuration
    LLM_PROVIDER = "openai"
    LLM_MODEL = "gpt-5.1-thinking"
    
    def __init__(self):
        self.telnet = TelnetClient("dunemud.net", 6789)
        self.gmcp = GMCPHandler()
        
        # Initialize LLM agent
        self.agent = LLMAgent(
            provider=self.LLM_PROVIDER,
            model=self.LLM_MODEL,
        )
        
        # State tracking
        self.output_buffer = []
        self.gmcp_messages = []
        self.rooms_visited = []
        self.commands_sent = []
        self.current_room_name = ""
        self.current_room_id = ""
        self.in_game = False
        
        # Goal tracking
        self.reached_guild = False
        self.joined_guild = False
        self.got_weapon = False
        
        # Register callbacks
        self.telnet.on_text(self._on_text)
        self.telnet.on_gmcp(self._on_gmcp)
        self.gmcp.on_room_change(self._on_room_change)
    
    async def _on_text(self, text: str) -> None:
        """Handle text received from server."""
        self.output_buffer.append(text)
        
        # Print received text (limited)
        for line in text.split('\n')[:10]:
            clean_line = self._strip_ansi(line).strip()
            if clean_line:
                logger.info(f"[MUD] {clean_line[:150]}")
        
        # Detect game state from text
        text_lower = text.lower()
        
        if "you have entered" in text_lower:
            self.in_game = True
            logger.info("GAME ENTRY DETECTED!")
        
        # Detect Atreides guild
        if "atreides" in text_lower and ("guild" in text_lower or "hall" in text_lower):
            self.reached_guild = True
            logger.info("ATREIDES GUILD DETECTED!")
        
        # Detect joining guild
        if "you are now a member" in text_lower or "welcome to the atreides" in text_lower:
            self.joined_guild = True
            logger.info("JOINED GUILD!")
        
        # Detect getting weapon
        if "you get" in text_lower or "you wield" in text_lower:
            if "sword" in text_lower or "knife" in text_lower or "blade" in text_lower or "weapon" in text_lower:
                self.got_weapon = True
                logger.info("GOT WEAPON!")
    
    async def _on_gmcp(self, module: str, data) -> None:
        """Handle GMCP messages."""
        self.gmcp_messages.append({
            "module": module,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        logger.debug(f"[GMCP] {module}: {data}")
        self.gmcp.process(module, data)
    
    def _on_room_change(self, room) -> None:
        """Handle room change event."""
        self.current_room_name = room.name
        self.current_room_id = room.num
        
        logger.info(f"[ROOM] {room.name} (Area: {room.area})")
        logger.info(f"  Exits: {list(room.exits.keys()) if room.exits else 'none'}")
        
        self.rooms_visited.append({
            "id": room.num,
            "name": room.name,
            "area": room.area,
            "exits": room.exits,
            "timestamp": datetime.now().isoformat(),
        })
        
        # Check if we reached Atreides guild
        if room.name and "atreides" in room.name.lower():
            self.reached_guild = True
            logger.info("ATREIDES GUILD ROOM DETECTED VIA GMCP!")
    
    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def _get_recent_output(self, lines: int = 50) -> str:
        """Get recent output text for context."""
        all_text = "\n".join(self.output_buffer[-20:])
        lines_list = all_text.split('\n')
        return "\n".join(lines_list[-lines:])
    
    async def receive_for(self, seconds: float) -> None:
        """Receive data for a period of time."""
        end = asyncio.get_event_loop().time() + seconds
        while asyncio.get_event_loop().time() < end:
            try:
                await self.telnet.receive()
            except:
                pass
            await asyncio.sleep(0.05)
    
    async def send_cmd(self, cmd: str, wait: float = 2.0) -> None:
        """Send command and wait for response."""
        logger.info(f"[SEND] {cmd}")
        self.commands_sent.append(cmd)
        await self.telnet.send(cmd)
        await self.receive_for(wait)
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the LLM agent."""
        return """You are an AI agent playing DuneMUD, a text-based multiplayer game set in the Dune universe.

Your current mission has THREE objectives in order:
1. Navigate to the Atreides Guild (go 6 rooms north from the starting position)
2. Join the Atreides guild (use the 'join' command)
3. Get a weapon from the guild armory (look for armory, get a weapon)

IMPORTANT RULES:
- Respond with ONLY a single MUD command, nothing else
- Valid movement commands: n, s, e, w, ne, nw, se, sw, u, d (or full words like north, south)
- To join a guild: 'join' or 'join atreides'
- To look around: 'look' or 'l'
- To get items: 'get <item>' or 'get all'
- To see what's available: 'list' or 'inventory'
- To enter places: 'enter <place>' or just the direction

Current status:
- Mission objective 1 (reach guild): {reached}
- Mission objective 2 (join guild): {joined}
- Mission objective 3 (get weapon): {weapon}

If you haven't reached the guild yet, keep going NORTH.
If you're at the guild but haven't joined, use 'join' or 'join atreides'.
If you've joined, look for the armory and get a weapon.

Respond with just the command, no explanation."""
    
    def _build_user_prompt(self) -> str:
        """Build the user prompt with current game context."""
        recent_output = self._get_recent_output(30)
        
        # Get current room info
        room_info = f"Current room: {self.current_room_name}" if self.current_room_name else "Room unknown"
        
        # Get recent rooms for navigation context
        recent_rooms = []
        for room in self.rooms_visited[-5:]:
            recent_rooms.append(f"- {room['name']}: exits {list(room['exits'].keys()) if room['exits'] else 'unknown'}")
        rooms_context = "\n".join(recent_rooms) if recent_rooms else "No rooms visited yet"
        
        return f"""Recent game output:
```
{recent_output}
```

{room_info}

Recent rooms visited:
{rooms_context}

Status:
- Reached Atreides Guild: {self.reached_guild}
- Joined Guild: {self.joined_guild}
- Got Weapon: {self.got_weapon}

What is your next command?"""
    
    async def get_ai_command(self) -> str:
        """Get the next command from the AI agent."""
        system_prompt = self._build_system_prompt().format(
            reached="YES" if self.reached_guild else "NO",
            joined="YES" if self.joined_guild else "NO",
            weapon="YES" if self.got_weapon else "NO",
        )
        user_prompt = self._build_user_prompt()
        
        try:
            response = await self.agent.get_command(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
            )
            
            logger.info(f"[AI] Command: {response.command} (tokens: {response.tokens_used})")
            return response.command
            
        except Exception as e:
            logger.error(f"AI error: {e}")
            # Fallback: if we haven't reached guild, go north
            if not self.reached_guild:
                return "n"
            elif not self.joined_guild:
                return "join"
            else:
                return "look"
    
    async def run(self) -> dict:
        """Run the agentic test."""
        results = {
            "success": False,
            "connected": False,
            "logged_in": False,
            "reached_guild": False,
            "joined_guild": False,
            "got_weapon": False,
            "rooms_visited": 0,
            "commands_sent": 0,
            "ai_model": self.LLM_MODEL,
            "issues": [],
        }
        
        try:
            # Connect
            logger.info("="*60)
            logger.info("ATREIDES GUILD AGENTIC TEST")
            logger.info(f"Using LLM: {self.LLM_PROVIDER} / {self.LLM_MODEL}")
            logger.info("="*60)
            
            logger.info("Connecting to dunemud.net:6789...")
            if not await self.telnet.connect():
                results["issues"].append("Failed to connect")
                return results
            
            results["connected"] = True
            
            # Wait for initial negotiation
            await self.receive_for(3)
            
            if not self.telnet.gmcp_enabled:
                logger.warning("GMCP not enabled")
            
            # Enable GMCP modules
            await self.telnet.send_gmcp("Core.Hello", {"client": "LLMUD-Agentic-Test", "version": "0.1"})
            await self.telnet.send_gmcp("Core.Supports.Set", ["Room 1", "Char 1"])
            await self.receive_for(1)
            
            # Login with credentials
            logger.info(f"Logging in as {self.USERNAME}...")
            await self.send_cmd(self.USERNAME, 2)
            await self.send_cmd(self.PASSWORD, 3)
            
            # Handle any login prompts
            await self.receive_for(2)
            
            results["logged_in"] = True
            logger.info("Login complete, starting agentic navigation...")
            
            # Initial look
            await self.send_cmd("look", 2)
            
            # Agentic loop - let the AI navigate
            max_iterations = 30
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"\n--- Iteration {iteration}/{max_iterations} ---")
                
                # Check if we've completed all objectives
                if self.reached_guild and self.joined_guild and self.got_weapon:
                    logger.info("ALL OBJECTIVES COMPLETE!")
                    break
                
                # Get AI command
                command = await self.get_ai_command()
                
                if command:
                    await self.send_cmd(command, 2.5)
                
                # Small delay between AI decisions
                await asyncio.sleep(0.5)
            
            # Final status
            results["reached_guild"] = self.reached_guild
            results["joined_guild"] = self.joined_guild
            results["got_weapon"] = self.got_weapon
            results["rooms_visited"] = len(self.rooms_visited)
            results["commands_sent"] = len(self.commands_sent)
            
            # Determine success
            if self.reached_guild and self.joined_guild and self.got_weapon:
                results["success"] = True
            elif self.reached_guild and self.joined_guild:
                # Partial success - joined but no weapon
                results["issues"].append("Joined guild but couldn't get weapon")
            elif self.reached_guild:
                results["issues"].append("Reached guild but couldn't join")
            else:
                results["issues"].append("Failed to reach Atreides guild")
            
        except Exception as e:
            import traceback
            logger.error(f"Test error: {e}")
            traceback.print_exc()
            results["issues"].append(f"Exception: {str(e)}")
        
        finally:
            logger.info("Disconnecting...")
            await self.telnet.disconnect()
        
        return results


async def main():
    """Main entry point."""
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable not set")
        print("Please set it before running this test:")
        print("  export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)
    
    tester = AtreidesGuildAgentTest()
    results = await tester.run()
    
    print("\n" + "="*60)
    print("ATREIDES GUILD AGENTIC TEST - FINAL RESULTS")
    print("="*60)
    print(f"AI Model: {results['ai_model']}")
    print(f"Connected: {results['connected']}")
    print(f"Logged In: {results['logged_in']}")
    print(f"Reached Guild: {results['reached_guild']}")
    print(f"Joined Guild: {results['joined_guild']}")
    print(f"Got Weapon: {results['got_weapon']}")
    print(f"Rooms Visited: {results['rooms_visited']}")
    print(f"Commands Sent: {results['commands_sent']}")
    print(f"\nOverall Success: {results['success']}")
    
    if results['issues']:
        print("\nISSUES:")
        for issue in results['issues']:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print("\nAll objectives completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
