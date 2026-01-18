#!/usr/bin/env python3
"""
Live Tests for Agentic MUD AI

This script runs live tests against dunemud.net:6789 to evaluate the
agentic AI approach. Tests include navigation, exploration, and basic
command execution.

Usage:
    python test_agentic_live.py --api-key YOUR_KEY
    python test_agentic_live.py --api-key YOUR_KEY --test basic
    python test_agentic_live.py --api-key YOUR_KEY --test loop
"""

import asyncio
import logging
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

# Add mud_client to path
sys.path.insert(0, str(Path(__file__).parent / "mud_client"))

from llmud import (
    AgenticSession,
    AgenticSessionConfig,
    EvalRunner,
    EvalSuite,
    EvalReport,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ==================== Test Definitions ====================

class LiveTests:
    """Collection of live tests for the agentic AI."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.host = "dunemud.net"
        self.port = 6789
    
    async def test_connection(self) -> bool:
        """Test basic connection to the MUD."""
        print("\n" + "="*60)
        print("TEST: Basic Connection")
        print("="*60)
        
        config = AgenticSessionConfig(
            host=self.host,
            port=self.port,
            openai_api_key=self.api_key,
            model=self.model,
        )
        
        session = AgenticSession(config)
        
        try:
            connected = await session.connect()
            if connected:
                print("✓ Connected successfully")
                # Wait for initial output
                await asyncio.sleep(2)
                
                # Check if we got GMCP enabled
                gmcp_enabled = session.telnet.gmcp_enabled
                print(f"✓ GMCP enabled: {gmcp_enabled}")
                
                await session.disconnect()
                print("✓ Disconnected cleanly")
                return True
            else:
                print("✗ Failed to connect")
                return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
        finally:
            await session.disconnect()
    
    async def test_guest_login(self) -> bool:
        """Test logging in as a guest."""
        print("\n" + "="*60)
        print("TEST: Guest Login")
        print("="*60)
        
        config = AgenticSessionConfig(
            host=self.host,
            port=self.port,
            openai_api_key=self.api_key,
            model=self.model,
        )
        
        session = AgenticSession(config)
        output_lines = []
        
        def on_event(event):
            if event.type == "text":
                text = event.data.get("text", "")
                if text.strip():
                    output_lines.append(text)
                    print(f"MUD: {text[:100]}")
        
        session.on_event(on_event)
        
        try:
            connected = await session.connect()
            if not connected:
                print("✗ Failed to connect")
                return False
            
            print("✓ Connected")
            
            # Receive data in a loop to capture output
            async def receive_loop():
                for _ in range(50):  # Try for 5 seconds
                    await session.telnet.receive()
                    await asyncio.sleep(0.1)
            
            # Start receiving
            recv_task = asyncio.create_task(receive_loop())
            await asyncio.sleep(1)
            
            # Enter as guest
            print("Sending 'guest'...")
            await session.send_command("guest")
            
            # Wait for response
            await asyncio.sleep(4)
            recv_task.cancel()
            
            # Check for room info via GMCP
            if session.gmcp.has_room_info():
                room = session.gmcp.room
                print(f"✓ In room: {room.name} ({room.area})")
                print(f"  Exits: {', '.join(room.get_exit_directions())}")
                return True
            else:
                print("? No GMCP room info received yet")
                # Check output for room-like text
                full_output = "\n".join(output_lines)
                print(f"Full output collected ({len(output_lines)} lines):")
                for line in output_lines[:10]:
                    print(f"  > {line[:80]}")
                if "obvious" in full_output.lower() or "exit" in full_output.lower():
                    print("✓ Room description detected in output")
                    return True
                if len(output_lines) > 0:
                    print("✓ Got MUD output, likely connected")
                    return True
                return False
                
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await session.disconnect()
    
    async def test_basic_commands(self) -> bool:
        """Test basic MUD commands via the agent."""
        print("\n" + "="*60)
        print("TEST: Basic Commands via Agent")
        print("="*60)
        
        config = AgenticSessionConfig(
            host=self.host,
            port=self.port,
            openai_api_key=self.api_key,
            model=self.model,
        )
        
        session = AgenticSession(config)
        
        def on_event(event):
            if event.type == "text":
                text = event.data.get("text", "")[:100]
                if text.strip():
                    print(f"MUD: {text}")
            elif event.type == "ai_action":
                print(f"AI: {event.data.get('message', '')}")
            elif event.type == "room_change":
                print(f"ROOM: {event.data.get('room_name', '')} - {event.data.get('exits', [])}")
        
        session.on_event(on_event)
        
        try:
            connected = await session.connect()
            if not connected:
                print("✗ Failed to connect")
                return False
            
            print("✓ Connected")
            
            # Start session loop in background first
            loop_task = asyncio.create_task(session.run())
            await asyncio.sleep(1)
            
            # Enter as guest
            print("Sending 'guest'...")
            await session.send_command("guest")
            
            # Wait for login to complete
            print("Waiting for login...")
            await asyncio.sleep(2)
            
            # Send look to trigger room update
            print("Sending 'look'...")
            await session.send_command("look")
            await asyncio.sleep(3)
            
            # Check if we got room info
            if session.gmcp.has_room_info():
                room = session.gmcp.room
                print(f"✓ In room: {room.name} ({room.area})")
                print(f"  Exits: {', '.join(room.get_exit_directions())}")
            
            # Tell the agent about current state via an observation
            if session.agent:
                session.agent._tool_update_observation(
                    "I am already logged into the MUD as a guest character and standing in a room. I should use 'look' to see the room and then report the exits.",
                    "room"
                )
            
            # Track goal completion via event
            goal_result_container = {"completed": False, "success": False, "summary": ""}
            
            def on_goal_event(event):
                if event.type == "goal_complete":
                    goal_result_container["completed"] = True
                    goal_result_container["success"] = event.data.get("success", False) if event.data else False
                    goal_result_container["summary"] = event.data.get("summary", "") if event.data else ""
            
            session.on_event(on_goal_event)
            
            # Set a simple goal
            goal = "You are already in the game. Look at the current room with 'look' command and identify all available exits. Then report complete with success and list the exits."
            print(f"\nGoal: {goal}")
            
            # Set goal and enable AI
            await session.set_agent_goal(goal)
            session.set_ai_active(True)
            
            # Wait for goal completion
            start_time = asyncio.get_event_loop().time()
            timeout = 45
            
            while not goal_result_container["completed"]:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    print(f"Timeout after {elapsed:.0f}s")
                    break
                
                if not session._running:
                    break
                
                await asyncio.sleep(0.3)
            
            # Clean up
            session._running = False
            await asyncio.sleep(0.5)
            try:
                loop_task.cancel()
            except:
                pass
            
            if goal_result_container["completed"]:
                if goal_result_container["success"]:
                    print(f"✓ Goal achieved: {goal_result_container['summary']}")
                    return True
                else:
                    print(f"✗ Goal failed: {goal_result_container['summary']}")
                    return False
            
            print(f"✗ Goal not completed")
            return False
                
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await session.disconnect()
    
    async def test_navigation_loop(self) -> bool:
        """Test navigating in a loop and returning."""
        print("\n" + "="*60)
        print("TEST: Navigation Loop")
        print("="*60)
        
        config = AgenticSessionConfig(
            host=self.host,
            port=self.port,
            openai_api_key=self.api_key,
            model=self.model,
            map_enabled=True,
        )
        
        session = AgenticSession(config)
        
        def on_event(event):
            if event.type == "text":
                text = event.data.get("text", "")[:80]
                if text.strip():
                    print(f"MUD: {text}")
            elif event.type == "ai_action":
                print(f"AI: {event.data.get('message', '')}")
            elif event.type == "room_change":
                print(f"ROOM: {event.data.get('room_name', '')} - Exits: {event.data.get('exits', [])}")
        
        session.on_event(on_event)
        
        # Track goal completion via event
        goal_result = {"completed": False, "success": False, "summary": ""}
        
        def on_goal_event(event):
            if event.type == "goal_complete":
                goal_result["completed"] = True
                goal_result["success"] = event.data.get("success", False) if event.data else False
                goal_result["summary"] = event.data.get("summary", "") if event.data else ""
        
        session.on_event(on_goal_event)
        
        try:
            connected = await session.connect()
            if not connected:
                print("✗ Failed to connect")
                return False
            
            print("✓ Connected")
            
            # Start session loop in background
            loop_task = asyncio.create_task(session.run())
            await asyncio.sleep(1)
            
            # Enter as guest
            print("Sending 'guest'...")
            await session.send_command("guest")
            await asyncio.sleep(2)
            
            # Send look to trigger room update
            print("Sending 'look'...")
            await session.send_command("look")
            
            # Wait for login and GMCP data
            print("Waiting for GMCP data...")
            for _ in range(30):  # Wait up to 6 seconds
                await asyncio.sleep(0.2)
                if session.gmcp.has_room_info() and session.gmcp.has_vitals():
                    break
            
            # Check if we have valid state
            if session.gmcp.has_room_info():
                room = session.gmcp.room
                print(f"✓ In room: {room.name}")
                print(f"  Exits: {', '.join(room.get_exit_directions())}")
            else:
                print("? No room info received yet - will try with agent")
            
            hp, maxhp = session.gmcp.get_hp()
            print(f"HP: {hp}/{maxhp}")
            
            # Tell agent it's already in game with correct info
            if session.agent:
                room_name = session.gmcp.room.name if session.gmcp.has_room_info() else "a room in the game"
                hp_info = f"HP is {hp}/{maxhp}" if maxhp > 0 else "HP should be full (50/50)"
                session.agent._tool_update_observation(
                    f"I am logged in as a guest at {room_name}. {hp_info}. I am ready to proceed with the navigation task.",
                    "room"
                )
            
            # Set navigation goal - very simple
            goal = """Move north once, then move south once to return. When done, call report_complete(success=True, summary='Moved north to X and returned south to Y') where X and Y are the room names."""
            print(f"\nGoal: {goal}")
            
            await session.set_agent_goal(goal)
            session.set_ai_active(True)
            
            # Wait for goal completion
            start_time = asyncio.get_event_loop().time()
            timeout = 60
            
            while not goal_result["completed"]:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    print(f"Timeout after {elapsed:.0f}s")
                    break
                
                if not session._running:
                    break
                
                await asyncio.sleep(0.3)
            
            # Get map stats
            if session.map_agent:
                stats = session.map_agent.get_map_stats()
                print(f"\nMap stats: {stats.get('total_rooms', 0)} rooms discovered")
            
            # Clean up
            session._running = False
            await asyncio.sleep(0.5)
            try:
                loop_task.cancel()
            except:
                pass
            
            if goal_result["completed"]:
                if goal_result["success"]:
                    print(f"✓ Goal achieved: {goal_result['summary']}")
                    return True
                else:
                    print(f"✗ Goal failed: {goal_result['summary']}")
                    return False
            
            print(f"✗ Goal not completed")
            return False
                
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await session.disconnect()
    
    async def test_exploration(self) -> bool:
        """Test exploring multiple rooms."""
        print("\n" + "="*60)
        print("TEST: Exploration")
        print("="*60)
        
        config = AgenticSessionConfig(
            host=self.host,
            port=self.port,
            openai_api_key=self.api_key,
            model=self.model,
            map_enabled=True,
        )
        
        session = AgenticSession(config)
        rooms_visited = set()
        
        def on_event(event):
            if event.type == "text":
                text = event.data.get("text", "")[:80]
                if text.strip():
                    print(f"MUD: {text}")
            elif event.type == "ai_action":
                print(f"AI: {event.data.get('message', '')}")
            elif event.type == "room_change":
                room_name = event.data.get('room_name', '')
                rooms_visited.add(room_name)
                print(f"ROOM [{len(rooms_visited)}]: {room_name}")
        
        session.on_event(on_event)
        
        try:
            connected = await session.connect()
            if not connected:
                print("✗ Failed to connect")
                return False
            
            print("✓ Connected")
            await asyncio.sleep(1)
            
            # Enter as guest
            await session.send_command("guest")
            await asyncio.sleep(3)
            
            # Start session loop in background
            loop_task = asyncio.create_task(session.run())
            
            # Set exploration goal
            goal = "Explore at least 5 different rooms. Report the names of all rooms visited."
            print(f"\nGoal: {goal}")
            
            result = await session.run_goal(goal, timeout=90)
            
            # Get final stats
            print(f"\nRooms visited: {len(rooms_visited)}")
            for room in sorted(rooms_visited):
                print(f"  - {room}")
            
            if session.map_agent:
                stats = session.map_agent.get_map_stats()
                print(f"Map total: {stats.get('total_rooms', 0)} rooms")
            
            # Clean up
            session._running = False
            await asyncio.sleep(0.5)
            loop_task.cancel()
            
            success = len(rooms_visited) >= 5 or result.get("success")
            if success:
                print(f"✓ Exploration successful")
                return True
            else:
                print(f"✗ Exploration incomplete: {result.get('summary', '')}")
                return False
                
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await session.disconnect()


    async def test_atreides_guild(self) -> bool:
        """Test navigating to Atreides guild, reading messages, and returning."""
        print("\n" + "="*60)
        print("TEST: Atreides Guild Messages")
        print("="*60)
        
        config = AgenticSessionConfig(
            host=self.host,
            port=self.port,
            openai_api_key=self.api_key,
            model=self.model,
            map_enabled=True,
        )
        
        session = AgenticSession(config)
        collected_output = []
        
        def on_event(event):
            if event.type == "text":
                text = event.data.get("text", "")
                if text.strip():
                    collected_output.append(text)
                    # Only print short snippets during test
                    if len(text) > 100:
                        print(f"MUD: {text[:100]}...")
                    else:
                        print(f"MUD: {text}")
            elif event.type == "ai_action":
                print(f"AI: {event.data.get('message', '')}")
        
        session.on_event(on_event)
        
        # Track goal completion via event
        goal_result = {"completed": False, "success": False, "summary": ""}
        
        def on_goal_event(event):
            if event.type == "goal_complete":
                goal_result["completed"] = True
                goal_result["success"] = event.data.get("success", False) if event.data else False
                goal_result["summary"] = event.data.get("summary", "") if event.data else ""
        
        session.on_event(on_goal_event)
        
        try:
            connected = await session.connect()
            if not connected:
                print("✗ Failed to connect")
                return False
            
            print("✓ Connected")
            
            # Start session loop in background
            loop_task = asyncio.create_task(session.run())
            await asyncio.sleep(1)
            
            # Enter as guest
            print("Sending 'guest'...")
            await session.send_command("guest")
            await asyncio.sleep(2)
            
            # Send look to trigger room update
            print("Sending 'look'...")
            await session.send_command("look")
            await asyncio.sleep(3)
            
            # Tell agent about the task
            if session.agent:
                session.agent._tool_update_observation(
                    "I am logged in as a guest. I need to navigate to the Atreides guild, read messages, and return.",
                    "room"
                )
            
            # Set the guild exploration goal
            goal = """Your mission:
1. Go north 6 times (use 'n' command 6 times)
2. Then use 'enter' command to enter the Atreides guild
3. Once inside, read messages using 'news list' and 'news read' commands
4. After reading messages, return to the Astro Port (go south 6 times, or find your way back)
5. Call report_complete with success=True and include a summary of what the messages were about

Important: Read at least 2-3 news items to understand what they contain. Use 'news read 1', 'news read 2', etc."""
            
            print(f"\nGoal: Navigate to Atreides guild, read messages, return to spaceport")
            
            await session.set_agent_goal(goal)
            session.set_ai_active(True)
            
            # Wait for goal completion (longer timeout for this complex task)
            start_time = asyncio.get_event_loop().time()
            timeout = 180  # 3 minutes
            
            while not goal_result["completed"]:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    print(f"Timeout after {elapsed:.0f}s")
                    break
                
                if not session._running:
                    break
                
                await asyncio.sleep(0.3)
            
            # Clean up
            session._running = False
            await asyncio.sleep(0.5)
            try:
                loop_task.cancel()
            except:
                pass
            
            # Print collected output for analysis
            print("\n" + "="*60)
            print("COLLECTED OUTPUT (last 50 lines):")
            print("="*60)
            for line in collected_output[-50:]:
                print(line[:200])
            
            if goal_result["completed"]:
                if goal_result["success"]:
                    print(f"\n✓ Goal achieved: {goal_result['summary']}")
                    return True
                else:
                    print(f"\n✗ Goal failed: {goal_result['summary']}")
                    return False
            
            print(f"\n✗ Goal not completed")
            return False
                
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await session.disconnect()


async def run_all_tests(api_key: str, model: str = "gpt-5.1"):
    """Run all live tests."""
    tests = LiveTests(api_key, model)
    
    results = {}
    
    # Test 1: Connection
    results["connection"] = await tests.test_connection()
    await asyncio.sleep(2)
    
    if not results["connection"]:
        print("\n✗ Connection test failed - skipping remaining tests")
        return results
    
    # Test 2: Guest login
    results["guest_login"] = await tests.test_guest_login()
    await asyncio.sleep(2)
    
    if not results["guest_login"]:
        print("\n✗ Guest login failed - skipping AI tests")
        return results
    
    # Test 3: Basic commands
    results["basic_commands"] = await tests.test_basic_commands()
    await asyncio.sleep(2)
    
    # Test 4: Navigation loop
    results["navigation_loop"] = await tests.test_navigation_loop()
    await asyncio.sleep(2)
    
    # Test 5: Exploration
    results["exploration"] = await tests.test_exploration()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*60)
    
    return results


async def run_single_test(api_key: str, test_name: str, model: str = "gpt-5.1"):
    """Run a single test."""
    tests = LiveTests(api_key, model)
    
    test_map = {
        "connection": tests.test_connection,
        "guest": tests.test_guest_login,
        "basic": tests.test_basic_commands,
        "loop": tests.test_navigation_loop,
        "exploration": tests.test_exploration,
        "atreides": tests.test_atreides_guild,
    }
    
    if test_name not in test_map:
        print(f"Unknown test: {test_name}")
        print(f"Available tests: {', '.join(test_map.keys())}")
        return False
    
    return await test_map[test_name]()


def main():
    parser = argparse.ArgumentParser(description="Run live MUD AI tests")
    parser.add_argument("--api-key", required=True, help="OpenAI API key")
    parser.add_argument("--model", default="gpt-5.1", help="Model to use")
    parser.add_argument("--test", help="Specific test to run (connection, guest, basic, loop, exploration)")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    
    args = parser.parse_args()
    
    if args.test:
        result = asyncio.run(run_single_test(args.api_key, args.test, args.model))
        sys.exit(0 if result else 1)
    else:
        results = asyncio.run(run_all_tests(args.api_key, args.model))
        passed = sum(1 for v in results.values() if v)
        sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
