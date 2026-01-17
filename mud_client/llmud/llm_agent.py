"""
LLM Agent - Interfaces with OpenAI or Anthropic for decision making.
"""

import os
import re
import json
import logging
import asyncio
from typing import Optional, Any, Literal
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM."""
    command: str
    raw_response: str
    model: str
    tokens_used: int = 0
    reasoning: str = ""


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""
    
    @abstractmethod
    async def complete(
        self, 
        system_prompt: str, 
        user_prompt: str,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Get completion from the LLM."""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider."""
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = None
        
        if not self.api_key:
            raise ValueError("OpenAI API key required")

    def _get_client(self):
        """Lazy load the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Get completion from OpenAI."""
        client = self._get_client()
        
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=150,  # Commands should be short
            )
            
            content = response.choices[0].message.content or ""
            command = self._extract_command(content)
            
            return LLMResponse(
                command=command,
                raw_response=content,
                model=self.model,
                tokens_used=response.usage.total_tokens if response.usage else 0,
            )
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _extract_command(self, response: str) -> str:
        """Extract command from LLM response."""
        # Clean up response
        response = response.strip()
        
        # Remove common prefixes
        prefixes = ["Command:", "Execute:", ">", "$"]
        for prefix in prefixes:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Take first line if multiple
        lines = response.split('\n')
        command = lines[0].strip()
        
        # Remove backticks if present
        command = command.strip('`')
        
        return command


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None
        
        if not self.api_key:
            raise ValueError("Anthropic API key required")

    def _get_client(self):
        """Lazy load the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
        return self._client

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Get completion from Anthropic."""
        client = self._get_client()
        
        try:
            response = await client.messages.create(
                model=self.model,
                max_tokens=150,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
            )
            
            content = response.content[0].text if response.content else ""
            command = self._extract_command(content)
            
            return LLMResponse(
                command=command,
                raw_response=content,
                model=self.model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            )
            
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def _extract_command(self, response: str) -> str:
        """Extract command from LLM response."""
        response = response.strip()
        
        # Remove common prefixes
        prefixes = ["Command:", "Execute:", ">", "$"]
        for prefix in prefixes:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Take first line if multiple
        lines = response.split('\n')
        command = lines[0].strip()
        
        # Remove backticks if present
        command = command.strip('`')
        
        return command


class LLMAgent:
    """
    High-level agent that uses LLM for decision making.
    Manages context and generates appropriate commands.
    """

    def __init__(
        self,
        provider: Literal["openai", "anthropic"] = "anthropic",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        if provider == "openai":
            self.provider = OpenAIProvider(
                api_key=api_key,
                model=model or "gpt-4o",
            )
        elif provider == "anthropic":
            self.provider = AnthropicProvider(
                api_key=api_key,
                model=model or "claude-sonnet-4-20250514",
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 0.5  # seconds
        
        # Command validation
        self._valid_commands = self._load_valid_commands()
        
        # History for learning
        self._command_history: list[dict] = []

    def _load_valid_commands(self) -> set[str]:
        """Load set of valid MUD commands."""
        # Basic movement
        commands = {
            "n", "s", "e", "w", "ne", "nw", "se", "sw", "u", "d",
            "north", "south", "east", "west", "up", "down",
            "northeast", "northwest", "southeast", "southwest",
        }
        
        # Basic actions
        commands.update({
            "look", "l", "score", "sc", "inventory", "i", "equipment", "eq",
            "who", "help", "quit", "brief", "exits",
        })
        
        # Combat
        commands.update({
            "kill", "flee", "consider", "wimpy", "aim",
        })
        
        # Communication
        commands.update({
            "say", "tell", "chat", "newbie", "reply",
        })
        
        # Other
        commands.update({
            "get", "drop", "wear", "wield", "remove", "unwield",
            "open", "close", "enter", "climb", "search",
            "deposit", "withdraw", "list", "order", "buy", "sell",
        })
        
        return commands

    async def get_command(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Get next command from the LLM."""
        # Rate limiting
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        
        try:
            response = await self.provider.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
            
            # Validate and clean command
            response.command = self._validate_command(response.command)
            
            # Store in history
            self._command_history.append({
                "command": response.command,
                "tokens": response.tokens_used,
            })
            
            self._last_request_time = time.time()
            return response
            
        except Exception as e:
            logger.error(f"LLM error: {e}")
            # Return safe fallback command
            return LLMResponse(
                command="look",
                raw_response=f"Error: {e}",
                model="fallback",
            )

    def _validate_command(self, command: str) -> str:
        """Validate and clean a command."""
        if not command:
            return "look"  # Safe default
        
        # Clean whitespace
        command = command.strip()
        
        # Extract first word to check validity
        parts = command.split()
        if not parts:
            return "look"
        
        base_cmd = parts[0].lower()
        
        # Check if it's a known command or looks like a command
        # Be permissive to allow guild-specific commands
        if base_cmd in self._valid_commands:
            return command
        
        # Allow commands that look like they could be valid
        # (guild commands, sequences, etc.)
        if re.match(r'^[a-zA-Z]+', base_cmd):
            return command
        
        # Default fallback
        logger.warning(f"Unknown command '{command}', using 'look'")
        return "look"

    async def get_action_buttons(
        self,
        context: str,
        room_exits: list[str],
        npcs: list[str],
        items: list[str],
        in_combat: bool = False,
    ) -> list[dict]:
        """Generate dynamic action buttons based on context."""
        buttons = []
        
        # Navigation buttons
        for exit_dir in room_exits:
            buttons.append({
                "label": exit_dir.upper(),
                "command": exit_dir,
                "type": "navigation",
                "style": "primary",
            })
        
        # NPC interaction buttons
        for npc in npcs[:3]:  # Limit to 3 NPCs
            buttons.append({
                "label": f"Consider {npc}",
                "command": f"consider {npc}",
                "type": "interaction",
                "style": "secondary",
            })
        
        # Combat buttons
        if in_combat:
            buttons.extend([
                {"label": "Flee", "command": "flee", "type": "combat", "style": "danger"},
            ])
        
        # Standard buttons
        buttons.extend([
            {"label": "Look", "command": "look", "type": "info", "style": "info"},
            {"label": "Score", "command": "score", "type": "info", "style": "info"},
            {"label": "Inventory", "command": "i", "type": "info", "style": "info"},
        ])
        
        return buttons

    async def generate_room_visualization_prompt(
        self,
        room_name: str,
        room_description: str,
        area: str,
        environment: str,
    ) -> str:
        """Generate a prompt for room visualization."""
        prompt = f"""Generate an image of a scene from the Dune universe:

Location: {room_name}
Planet/Area: {area}
Setting: {environment}
Description: {room_description}

Style: Cinematic, atmospheric, inspired by the Dune aesthetic with desert tones, 
dramatic lighting, and a sense of vast scale. Include architectural elements 
consistent with the Dune universe (Fremen sietches, Arrakeen palaces, guild ships, etc.)
"""
        return prompt

    def get_stats(self) -> dict:
        """Get agent statistics."""
        total_tokens = sum(c["tokens"] for c in self._command_history)
        return {
            "total_commands": len(self._command_history),
            "total_tokens": total_tokens,
            "avg_tokens_per_command": total_tokens / len(self._command_history) if self._command_history else 0,
        }
