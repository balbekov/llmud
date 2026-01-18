"""
Tests for LLM integration using OpenAI API.

These tests verify that we can:
1. Use OpenAI to summarize the current room
2. Generate actions based on game state
3. Process LLM responses correctly
"""

import asyncio
import os
import pytest

pytestmark = pytest.mark.asyncio


class TestOpenAIProvider:
    """Tests for OpenAI provider functionality."""

    async def test_openai_provider_initialization(self, openai_api_key):
        """Test that OpenAI provider initializes correctly."""
        from llmud.llm_agent import OpenAIProvider
        
        provider = OpenAIProvider(api_key=openai_api_key)
        assert provider.api_key == openai_api_key
        assert provider.model == "gpt-4o"

    async def test_openai_provider_custom_model(self, openai_api_key):
        """Test OpenAI provider with custom model."""
        from llmud.llm_agent import OpenAIProvider
        
        provider = OpenAIProvider(api_key=openai_api_key, model="gpt-4o-mini")
        assert provider.model == "gpt-4o-mini"

    async def test_openai_completion(self, openai_api_key):
        """Test getting a completion from OpenAI."""
        from llmud.llm_agent import OpenAIProvider
        
        provider = OpenAIProvider(api_key=openai_api_key, model="gpt-4o-mini")
        
        response = await provider.complete(
            system_prompt="You are a helpful assistant. Respond with only 'hello'.",
            user_prompt="Say hello",
            temperature=0.0,
        )
        
        assert response.command is not None
        assert response.model == "gpt-4o-mini"
        assert response.tokens_used > 0


class TestRoomSummarization:
    """Tests for room summarization using OpenAI."""

    async def test_summarize_room_description(self, openai_api_key):
        """Test summarizing a MUD room description."""
        from llmud.llm_agent import OpenAIProvider
        
        provider = OpenAIProvider(api_key=openai_api_key, model="gpt-4o-mini")
        
        room_description = """
        The Great Hall of Arrakeen
        
        You stand in the magnificent Great Hall of the Atreides palace on Arrakis.
        Tall stone columns rise to support a vaulted ceiling decorated with the 
        hawk crest of House Atreides. Glowglobes hover near the ceiling, casting
        a warm amber light across the polished stone floor. To the north, massive
        bronze doors lead to the courtyard. An archway to the east opens to the
        private chambers. Servants move quietly about their duties.
        
        Obvious exits: north, east, south
        A palace guard is standing here.
        A serving girl is here, carrying a tray.
        """
        
        response = await provider.complete(
            system_prompt="""You are a game assistant. Summarize the room in one 
            concise sentence focusing on: location name, key features, and available 
            exits. Be brief.""",
            user_prompt=f"Summarize this room:\n{room_description}",
            temperature=0.3,
        )
        
        assert response.raw_response is not None
        assert len(response.raw_response) > 0
        
        # Summary should mention key elements
        summary_lower = response.raw_response.lower()
        assert any(word in summary_lower for word in ["hall", "arrakeen", "palace", "atreides"])

    async def test_extract_room_info(self, openai_api_key):
        """Test extracting structured info from room description."""
        from llmud.llm_agent import OpenAIProvider
        import json
        
        provider = OpenAIProvider(api_key=openai_api_key, model="gpt-4o-mini")
        
        room_description = """
        Sietch Tabr - Water Storage
        
        Deep within the sietch, you find yourself in the water storage chamber.
        Massive cisterns line the walls, holding the tribe's most precious resource.
        The air is cool and damp here, a stark contrast to the desert above.
        A Fremen water master stands guard over the tribal wealth.
        
        Obvious exits: west, down
        A water master is here.
        Several stillsuit-clad Fremen are checking the cisterns.
        """
        
        response = await provider.complete(
            system_prompt="""Extract room information as JSON with these fields:
            - name: room name
            - exits: list of exit directions
            - npcs: list of NPCs present
            Respond with ONLY valid JSON, no explanation.""",
            user_prompt=f"Extract info from:\n{room_description}",
            temperature=0.0,
        )
        
        # Should get parseable response
        assert response.raw_response is not None
        
        # Try to extract JSON from response
        raw = response.raw_response.strip()
        # Handle markdown code blocks
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        
        try:
            data = json.loads(raw)
            assert "exits" in data or "name" in data
        except json.JSONDecodeError:
            # Even if not valid JSON, should have relevant content
            assert any(word in response.raw_response.lower() for word in [
                "west", "down", "sietch", "tabr"
            ])


class TestActionGeneration:
    """Tests for action generation using OpenAI."""

    async def test_generate_exploration_action(self, openai_api_key):
        """Test generating an exploration action."""
        from llmud.llm_agent import LLMAgent
        
        agent = LLMAgent(provider="openai", api_key=openai_api_key, model="gpt-4o-mini")
        
        system_prompt = """You are playing a MUD game. Your goal is to explore.
        Output ONLY the command to execute, nothing else.
        Valid movement commands: n, s, e, w, ne, nw, se, sw, u, d
        Valid info commands: look, score, inventory"""
        
        user_prompt = """## Current Room
        Crossroads
        You stand at a crossroads in the desert.
        Obvious exits: north, south, east, west
        
        What command should you execute to explore?"""
        
        response = await agent.get_command(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
        )
        
        assert response.command is not None
        
        # Should be a valid movement or info command
        valid_commands = ["n", "s", "e", "w", "north", "south", "east", "west",
                        "ne", "nw", "se", "sw", "look", "score", "inventory"]
        command_base = response.command.split()[0].lower()
        assert command_base in valid_commands, \
            f"Expected valid command, got: {response.command}"

    async def test_generate_combat_action(self, openai_api_key):
        """Test generating a combat-related action."""
        from llmud.llm_agent import LLMAgent
        
        agent = LLMAgent(provider="openai", api_key=openai_api_key, model="gpt-4o-mini")
        
        system_prompt = """You are playing a MUD game. 
        When you see a weak enemy, consider attacking.
        When HP is low, flee.
        Output ONLY the command to execute, nothing else.
        Combat commands: kill <target>, consider <target>, flee"""
        
        user_prompt = """## Current State
        HP: 150/200 (75%)
        
        ## Current Room
        Desert Path
        A small sand rat scurries about, looking harmless.
        Obvious exits: north, south
        
        A sand rat is here.
        
        What command should you execute?"""
        
        response = await agent.get_command(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
        )
        
        assert response.command is not None
        
        # Should be a reasonable action
        command_lower = response.command.lower()
        valid_actions = ["consider", "kill", "look", "n", "s", "north", "south"]
        assert any(action in command_lower for action in valid_actions), \
            f"Expected valid action, got: {response.command}"

    async def test_generate_flee_action(self, openai_api_key):
        """Test that AI flees when HP is critically low."""
        from llmud.llm_agent import LLMAgent
        
        agent = LLMAgent(provider="openai", api_key=openai_api_key, model="gpt-4o-mini")
        
        system_prompt = """You are playing a MUD game. 
        CRITICAL RULE: When HP is below 30%, you MUST flee immediately.
        Output ONLY the command: flee
        No other commands when HP is critical."""
        
        user_prompt = """## Current State
        HP: 25/200 (12%) - CRITICAL!
        You are in combat!
        
        ## Combat Log
        The giant worm hits you hard!
        You are badly wounded!
        
        What command should you execute? (HP is critical, you must flee)"""
        
        response = await agent.get_command(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,  # Deterministic
        )
        
        assert response.command is not None
        # Should flee or try to escape
        command_lower = response.command.lower()
        assert "flee" in command_lower or "run" in command_lower, \
            f"Expected flee command when HP critical, got: {response.command}"


class TestLLMWithMudSession:
    """Integration tests combining LLM with MUD session."""

    async def test_llm_agent_with_live_game(self, session_config, openai_api_key):
        """Test LLM agent making decisions with live game data."""
        from llmud import MUDSession
        
        # Update config to use OpenAI
        session_config.llm_provider = "openai"
        session_config.llm_api_key = openai_api_key
        
        session = MUDSession(session_config)
        
        collected_text = []
        
        def event_handler(event):
            if event.type == "text":
                collected_text.append(event.data.get("text", ""))
        
        session.on_event(event_handler)
        
        # Connect and login
        await session.connect()
        
        for _ in range(30):
            await session.telnet.receive()
        
        await session.login()
        
        await asyncio.sleep(2)
        for _ in range(50):
            await session.telnet.receive()
        
        # Build context from collected text
        game_output = "\n".join(collected_text[-20:])
        
        # Use context manager to build prompt
        session.context.add_output(game_output)
        
        # Get AI decision
        system_prompt = session.context.get_system_prompt()
        user_prompt = session.context.build_user_prompt()
        
        agent = session._get_agent()
        response = await agent.get_command(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        assert response.command is not None
        assert len(response.command) > 0
        
        # Command should be reasonable
        print(f"AI suggested command: {response.command}")
        
        await session.disconnect()

    async def test_context_manager_prompt_building(self, openai_api_key):
        """Test that context manager builds effective prompts."""
        from llmud.context_manager import ContextManager
        from llmud.llm_agent import LLMAgent
        
        context = ContextManager()
        
        # Simulate game state updates
        context.update_game_state({
            "character": {
                "name": "Dentrifier",
                "guild": "Fremen",
                "level": 10,
                "hp": 100,
                "hp_percent": 80,
                "cp": 50,
                "cp_percent": 60,
                "money": 500,
                "bank": 1000,
                "wimpy": 75,
            },
            "stats": {
                "str": 15, "con": 14, "int": 12,
                "wis": 13, "dex": 16, "qui": 15,
            }
        })
        
        context.update_current_room({
            "name": "Sietch Entrance",
            "area": "arrakis",
            "environment": "indoors",
            "exits": ["north", "east", "down"],
        }, "You stand at the entrance of a Fremen sietch. Sandy corridors lead deeper.")
        
        context.add_output("Welcome back to Sietch Tabr.")
        context.add_output("A Fremen guard nods at you.")
        
        # Build prompts
        system_prompt = context.get_system_prompt()
        user_prompt = context.build_user_prompt()
        
        assert "Dentrifier" in user_prompt or "character" in user_prompt.lower()
        assert any(exit_dir in user_prompt for exit_dir in ["north", "east", "down"])
        
        # Test with LLM
        agent = LLMAgent(provider="openai", api_key=openai_api_key, model="gpt-4o-mini")
        response = await agent.get_command(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        assert response.command is not None
        print(f"Generated command from context: {response.command}")

