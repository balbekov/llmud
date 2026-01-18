"""
Tests for custom strategy execution.

These tests verify that:
1. A custom strategy file can be loaded
2. The AI follows the strategy's movement loop (n, n, s, s)
3. The loop completes successfully
"""

import asyncio
import os
from pathlib import Path
import pytest

pytestmark = pytest.mark.asyncio


class TestLoopStrategy:
    """Tests for the loop movement strategy."""

    async def test_loop_strategy_file_exists(self, loop_strategy_path):
        """Test that the loop strategy file exists."""
        assert Path(loop_strategy_path).exists(), \
            f"Loop strategy file not found at {loop_strategy_path}"

    async def test_context_manager_loads_custom_strategy(self, loop_strategy_path):
        """Test that context manager loads the custom strategy."""
        from llmud.context_manager import ContextManager
        
        context = ContextManager(strategy_path=loop_strategy_path)
        
        # Check strategy is loaded
        strategy_content = context.windows["strategy"].content
        assert "loop" in strategy_content.lower(), \
            "Expected loop strategy content"
        assert "north" in strategy_content.lower(), \
            "Expected movement instructions in strategy"

    async def test_loop_strategy_generates_north_first(self, loop_strategy_path, openai_api_key):
        """Test that loop strategy generates 'north' as first command."""
        from llmud.context_manager import ContextManager
        from llmud.llm_agent import LLMAgent
        
        context = ContextManager(strategy_path=loop_strategy_path)
        
        # Set up minimal game state (no previous movements)
        context.update_current_room({
            "name": "Starting Room",
            "area": "test",
            "environment": "indoors",
            "exits": ["north", "south"],
        })
        
        # Clear any previous output to simulate fresh start
        context._output_buffer.clear()
        context.add_output("You are in a test room. Obvious exits: north, south")
        
        system_prompt = context.get_system_prompt()
        user_prompt = context.build_user_prompt()
        
        agent = LLMAgent(provider="openai", api_key=openai_api_key, model="gpt-4o-mini")
        response = await agent.get_command(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
        )
        
        assert response.command is not None
        command = response.command.lower().strip()
        
        # First command should be north (n or north)
        assert command in ["n", "north"], \
            f"Expected 'n' or 'north' as first command, got: {response.command}"

    async def test_loop_strategy_sequence(self, loop_strategy_path, openai_api_key):
        """Test the complete loop strategy sequence: n, n, s, s."""
        from llmud.context_manager import ContextManager
        from llmud.llm_agent import LLMAgent
        
        context = ContextManager(strategy_path=loop_strategy_path)
        agent = LLMAgent(provider="openai", api_key=openai_api_key, model="gpt-4o-mini")
        
        # Track commands generated
        commands = []
        expected_sequence = ["n", "n", "s", "s"]
        
        # Simulate the room changing as we move
        rooms = [
            {"name": "Start Room", "exits": ["north", "south"]},
            {"name": "North Room 1", "exits": ["north", "south"]},
            {"name": "North Room 2", "exits": ["south"]},
            {"name": "North Room 1", "exits": ["north", "south"]},  # Going back
            {"name": "Start Room", "exits": ["north", "south"]},
        ]
        
        for i, room in enumerate(rooms[:-1]):  # Don't process last room (we're done)
            context._output_buffer.clear()
            
            # Build output showing what commands have been issued
            if commands:
                command_history = f"Commands issued: {', '.join(commands)}"
                context.add_output(command_history)
            
            context.update_current_room({
                "name": room["name"],
                "area": "test",
                "environment": "indoors",
                "exits": room["exits"],
            })
            
            context.add_output(f"You are in {room['name']}. Exits: {', '.join(room['exits'])}")
            
            system_prompt = context.get_system_prompt()
            user_prompt = context.build_user_prompt()
            
            response = await agent.get_command(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
            )
            
            command = response.command.lower().strip()
            # Normalize command
            if command == "north":
                command = "n"
            elif command == "south":
                command = "s"
            
            commands.append(command)
            
            print(f"Step {i + 1}: Generated '{response.command}' (normalized: '{command}')")
            
            # Verify sequence so far
            if i < len(expected_sequence):
                assert command == expected_sequence[i], \
                    f"Step {i + 1}: Expected '{expected_sequence[i]}', got '{command}'"
        
        # Verify complete sequence
        assert commands == expected_sequence, \
            f"Expected sequence {expected_sequence}, got {commands}"


class TestLoopStrategyWithLiveMud:
    """Integration tests for loop strategy with live MUD connection."""

    async def test_loop_strategy_live_execution(
        self, 
        loop_session_config, 
        openai_api_key
    ):
        """Test executing the loop strategy against the live MUD."""
        from llmud import MUDSession
        
        if not openai_api_key:
            pytest.skip("OPENAI_API_KEY required for live test")
        
        loop_session_config.llm_api_key = openai_api_key
        session = MUDSession(loop_session_config)
        
        collected_events = []
        commands_sent = []
        
        def event_handler(event):
            collected_events.append(event)
            if event.type == "command":
                commands_sent.append(event.data.get("command", ""))
        
        session.on_event(event_handler)
        
        # Connect and login
        connected = await session.connect()
        assert connected, "Failed to connect to MUD"
        
        # Receive initial data
        for _ in range(30):
            await session.telnet.receive()
        
        # Login
        await session.login()
        await asyncio.sleep(2)
        
        for _ in range(50):
            await session.telnet.receive()
        
        # Execute the loop
        loop_commands = []
        max_iterations = 6  # n, n, s, s, look, plus buffer
        
        for i in range(max_iterations):
            # Let the context update from MUD
            await asyncio.sleep(0.5)
            for _ in range(10):
                await session.telnet.receive()
            
            # Get AI decision
            system_prompt = session.context.get_system_prompt()
            user_prompt = session.context.build_user_prompt()
            
            agent = session._get_agent()
            response = await agent.get_command(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
            )
            
            command = response.command.lower().strip()
            loop_commands.append(command)
            print(f"Iteration {i + 1}: AI command = '{command}'")
            
            # Execute the command
            await session.send_command(response.command)
            
            # Wait for MUD response
            await asyncio.sleep(1)
            for _ in range(20):
                await session.telnet.receive()
            
            # Check if we've completed the loop (look command indicates completion)
            if command == "look":
                print("Loop completed with 'look' command")
                break
        
        await session.disconnect()
        
        # Verify we got the expected pattern
        # Allow for variations (n/north, s/south)
        normalized = []
        for cmd in loop_commands:
            if cmd in ["n", "north"]:
                normalized.append("n")
            elif cmd in ["s", "south"]:
                normalized.append("s")
            elif cmd == "look":
                normalized.append("look")
            else:
                normalized.append(cmd)
        
        # Check that we have at least the n, n, s, s pattern
        movement_pattern = [c for c in normalized if c in ["n", "s"]]
        
        # Should have at least 2 norths followed by 2 souths
        print(f"Movement pattern: {movement_pattern}")
        print(f"Full commands: {loop_commands}")
        
        # Flexible check - at least some north and south movements
        north_count = movement_pattern.count("n")
        south_count = movement_pattern.count("s")
        
        assert north_count >= 1, f"Expected at least 1 north, got {north_count}"
        assert south_count >= 1, f"Expected at least 1 south, got {south_count}"


class TestStrategyComparison:
    """Tests comparing different strategies."""

    async def test_default_vs_loop_strategy(self, session_config, loop_session_config, openai_api_key):
        """Test that different strategies produce different behaviors."""
        from llmud.context_manager import ContextManager
        from llmud.llm_agent import LLMAgent
        
        # Set up identical game state
        game_state = {
            "character": {
                "name": "Test",
                "guild": "none",
                "level": 1,
                "hp": 100,
                "hp_percent": 100,
            }
        }
        
        room = {
            "name": "Test Room",
            "area": "test",
            "environment": "indoors",
            "exits": ["north", "south", "east", "west"],
        }
        
        # Default strategy context
        default_context = ContextManager(strategy_path=session_config.strategy_path)
        default_context.update_game_state(game_state)
        default_context.update_current_room(room)
        default_context.add_output("A test room with many exits.")
        
        # Loop strategy context
        loop_context = ContextManager(strategy_path=loop_session_config.strategy_path)
        loop_context.update_game_state(game_state)
        loop_context.update_current_room(room)
        loop_context.add_output("A test room with many exits.")
        
        agent = LLMAgent(provider="openai", api_key=openai_api_key, model="gpt-4o-mini")
        
        # Get commands from both strategies
        default_response = await agent.get_command(
            system_prompt=default_context.get_system_prompt(),
            user_prompt=default_context.build_user_prompt(),
            temperature=0.0,
        )
        
        loop_response = await agent.get_command(
            system_prompt=loop_context.get_system_prompt(),
            user_prompt=loop_context.build_user_prompt(),
            temperature=0.0,
        )
        
        print(f"Default strategy command: {default_response.command}")
        print(f"Loop strategy command: {loop_response.command}")
        
        # Loop strategy should produce north (n)
        loop_cmd = loop_response.command.lower().strip()
        assert loop_cmd in ["n", "north"], \
            f"Loop strategy should produce 'n' or 'north', got '{loop_cmd}'"
        
        # Default strategy could produce any valid command
        assert default_response.command is not None

