"""
Context Manager - Manages LLM context with efficient token usage.

The strategy is to keep the high-level strategy document always in context,
while rotating recent game output, room descriptions, and combat logs.
"""

import os
import logging
from typing import Optional, Any
from dataclasses import dataclass, field
from collections import deque
from pathlib import Path

logger = logging.getLogger(__name__)

# Approximate token counts (rough estimates)
TOKENS_PER_CHAR = 0.25  # Rough estimate for English text


@dataclass
class ContextWindow:
    """Represents a segment of context."""
    name: str
    content: str
    priority: int  # Higher = more important to keep
    max_tokens: int
    current_tokens: int = 0
    
    def update_token_count(self) -> None:
        """Update the estimated token count."""
        self.current_tokens = int(len(self.content) * TOKENS_PER_CHAR)


class ContextManager:
    """
    Manages context for LLM interactions with efficient token usage.
    
    Context priorities:
    1. Strategy document (always present)
    2. Current game state (HP, location, etc.)
    3. Current room description
    4. Recent output (last few lines)
    5. Recent room history (for navigation)
    6. Combat history (when in combat)
    """

    # Default token budgets (conservative for Claude/GPT-4)
    DEFAULT_BUDGETS = {
        "strategy": 4000,
        "game_state": 500,
        "current_room": 800,
        "recent_output": 2000,
        "room_history": 1000,
        "combat_log": 500,
        "world_map": 1000,
    }

    def __init__(
        self,
        strategy_path: Optional[str] = None,
        max_total_tokens: int = 12000,
        budgets: Optional[dict[str, int]] = None,
    ):
        self.max_total_tokens = max_total_tokens
        self.budgets = budgets or self.DEFAULT_BUDGETS.copy()
        
        # Context windows
        self.windows: dict[str, ContextWindow] = {}
        
        # Load strategy document
        self._load_strategy(strategy_path)
        
        # Initialize other windows
        self._init_windows()
        
        # Rolling buffers for dynamic content
        self._output_buffer: deque[str] = deque(maxlen=100)
        self._room_buffer: deque[dict] = deque(maxlen=20)
        self._combat_buffer: deque[str] = deque(maxlen=50)

    def _load_strategy(self, path: Optional[str]) -> None:
        """Load the strategy document."""
        strategy_content = ""
        
        if path:
            try:
                strategy_content = Path(path).read_text()
                logger.info(f"Loaded strategy from {path}")
            except Exception as e:
                logger.warning(f"Could not load strategy from {path}: {e}")
        
        if not strategy_content:
            # Try default location
            default_path = Path(__file__).parent.parent.parent / "strategy.md"
            if default_path.exists():
                strategy_content = default_path.read_text()
                logger.info(f"Loaded strategy from {default_path}")
            else:
                # Use minimal embedded strategy
                strategy_content = self._get_minimal_strategy()
                logger.warning("Using minimal embedded strategy")
        
        self.windows["strategy"] = ContextWindow(
            name="Strategy",
            content=strategy_content,
            priority=100,
            max_tokens=self.budgets["strategy"],
        )
        self.windows["strategy"].update_token_count()

    def _get_minimal_strategy(self) -> str:
        """Get a minimal embedded strategy."""
        return """
# DuneMUD AI Strategy (Minimal)

## Key Commands
- Movement: n/s/e/w/ne/nw/se/sw/u/d
- Combat: kill <target>, flee, consider <target>
- Info: look, score, inventory, equipment
- Communication: say, tell <player>, chat

## Core Loop
1. Check HP - heal if below 50%
2. Consider targets before attacking
3. Set wimpy to 75 to auto-flee
4. Bank money at AstroPort (AP)
5. Don't attack mobs much stronger than you

## Recovery
- If dead: buy ghola at regeneration center
- If lost: find AstroPort and reorient
- If low HP: flee and heal
"""

    def _init_windows(self) -> None:
        """Initialize context windows."""
        for name in ["game_state", "current_room", "recent_output", 
                     "room_history", "combat_log", "world_map"]:
            self.windows[name] = ContextWindow(
                name=name,
                content="",
                priority=self._get_priority(name),
                max_tokens=self.budgets.get(name, 500),
            )

    def _get_priority(self, name: str) -> int:
        """Get priority for a context window."""
        priorities = {
            "strategy": 100,
            "game_state": 90,
            "current_room": 80,
            "recent_output": 70,
            "combat_log": 75,  # Higher during combat
            "room_history": 50,
            "world_map": 40,
        }
        return priorities.get(name, 30)

    def update_game_state(self, state: dict) -> None:
        """Update game state context."""
        content = "## Current Game State\n"
        
        if "character" in state:
            char = state["character"]
            content += f"""
### Character: {char.get('name', 'Unknown')}
- Guild: {char.get('guild', 'none')}
- Level: {char.get('level', 1)}
- HP: {char.get('hp', '?')} ({char.get('hp_percent', 0)}%)
- CP: {char.get('cp', '?')} ({char.get('cp_percent', 0)}%)
- Money: {char.get('money', 0)} (Bank: {char.get('bank', 0)})
- Wimpy: {char.get('wimpy', 0)}%
"""
        
        if "stats" in state:
            stats = state["stats"]
            content += f"""
### Stats
- STR: {stats.get('str', 0)} | CON: {stats.get('con', 0)}
- INT: {stats.get('int', 0)} | WIS: {stats.get('wis', 0)}
- DEX: {stats.get('dex', 0)} | QUI: {stats.get('qui', 0)}
"""
        
        self.windows["game_state"].content = content
        self.windows["game_state"].update_token_count()

    def update_current_room(self, room: dict, text: str = "") -> None:
        """Update current room context."""
        content = "## Current Room\n"
        content += f"**{room.get('name', 'Unknown')}** ({room.get('area', 'unknown')})\n"
        content += f"Environment: {room.get('environment', 'unknown')}\n"
        content += f"Exits: {', '.join(room.get('exits', ['none']))}\n"
        
        if text:
            # Include the actual room description (truncated if needed)
            max_desc = 500
            if len(text) > max_desc:
                text = text[:max_desc] + "..."
            content += f"\n### Description\n{text}\n"
        
        self.windows["current_room"].content = content
        self.windows["current_room"].update_token_count()
        
        # Add to room history buffer
        self._room_buffer.append({
            "name": room.get("name", ""),
            "area": room.get("area", ""),
            "exits": room.get("exits", []),
        })
        self._update_room_history()

    def add_output(self, text: str) -> None:
        """Add game output to the buffer."""
        if text.strip():
            self._output_buffer.append(text)
            self._update_recent_output()

    def add_combat_log(self, text: str) -> None:
        """Add combat-related text to combat buffer."""
        if text.strip():
            self._combat_buffer.append(text)
            self._update_combat_log()

    def _update_recent_output(self) -> None:
        """Update recent output context from buffer."""
        # Take last N lines that fit in budget
        recent = list(self._output_buffer)[-30:]
        content = "## Recent Game Output\n```\n"
        content += "\n".join(recent)
        content += "\n```"
        
        # Truncate if needed
        max_chars = int(self.budgets["recent_output"] / TOKENS_PER_CHAR)
        if len(content) > max_chars:
            content = content[-max_chars:]
        
        self.windows["recent_output"].content = content
        self.windows["recent_output"].update_token_count()

    def _update_room_history(self) -> None:
        """Update room history context."""
        content = "## Recent Rooms Visited\n"
        for i, room in enumerate(list(self._room_buffer)[-5:]):
            content += f"{i+1}. {room['name']} ({room['area']}) - Exits: {', '.join(room['exits'])}\n"
        
        self.windows["room_history"].content = content
        self.windows["room_history"].update_token_count()

    def _update_combat_log(self) -> None:
        """Update combat log context."""
        if not self._combat_buffer:
            self.windows["combat_log"].content = ""
            return
        
        content = "## Recent Combat\n```\n"
        content += "\n".join(list(self._combat_buffer)[-20:])
        content += "\n```"
        
        self.windows["combat_log"].content = content
        self.windows["combat_log"].update_token_count()

    def update_world_map(self, world_map: dict) -> None:
        """Update world map context (summarized)."""
        if not world_map:
            return
        
        # Group rooms by area
        areas: dict[str, list] = {}
        for room_id, room in world_map.items():
            area = room.area
            if area not in areas:
                areas[area] = []
            areas[area].append(room.name)
        
        content = "## Explored Areas\n"
        for area, rooms in sorted(areas.items()):
            room_count = len(rooms)
            sample = rooms[:3]
            content += f"- **{area}**: {room_count} rooms (e.g., {', '.join(sample)})\n"
        
        # Truncate if needed
        max_chars = int(self.budgets["world_map"] / TOKENS_PER_CHAR)
        if len(content) > max_chars:
            content = content[:max_chars] + "..."
        
        self.windows["world_map"].content = content
        self.windows["world_map"].update_token_count()

    def set_combat_mode(self, in_combat: bool) -> None:
        """Adjust priorities for combat mode."""
        if in_combat:
            self.windows["combat_log"].priority = 85  # Higher priority
            self.windows["room_history"].priority = 40
        else:
            self.windows["combat_log"].priority = 60
            self.windows["room_history"].priority = 50

    def build_context(self, include_strategy: bool = True) -> str:
        """Build the full context string for the LLM."""
        # Sort windows by priority
        sorted_windows = sorted(
            self.windows.values(),
            key=lambda w: w.priority,
            reverse=True
        )
        
        context_parts = []
        total_tokens = 0
        
        for window in sorted_windows:
            if not window.content:
                continue
            
            if not include_strategy and window.name == "strategy":
                continue
            
            # Check if we have room
            if total_tokens + window.current_tokens > self.max_total_tokens:
                # Try to include truncated version
                available = self.max_total_tokens - total_tokens
                if available > 100:  # Minimum useful content
                    max_chars = int(available / TOKENS_PER_CHAR)
                    truncated = window.content[:max_chars] + "..."
                    context_parts.append(truncated)
                break
            
            context_parts.append(window.content)
            total_tokens += window.current_tokens
        
        return "\n\n---\n\n".join(context_parts)

    def get_system_prompt(self) -> str:
        """Get the system prompt for the LLM."""
        return """You are an AI playing DuneMUD, a text-based multiplayer game set in the Dune universe.

Your role is to:
1. Read and understand game output
2. Make strategic decisions based on the provided strategy
3. Issue commands to navigate, fight, and progress

IMPORTANT RULES:
- Only output valid MUD commands (one per response unless using 'seq')
- Prioritize survival (check HP, flee if needed)
- Be efficient with commands
- Don't make assumptions about game state - use 'look' and 'score' to verify

Response format:
- Output ONLY the command(s) to execute
- For multiple commands, use: seq command1,command2,command3
- Do NOT include explanations in your response
- If you need information, use appropriate info commands (look, score, inventory, etc.)
"""

    def build_user_prompt(self, task: str = "") -> str:
        """Build a user prompt for the LLM."""
        context = self.build_context()
        
        prompt = f"{context}\n\n"
        prompt += "---\n\n"
        
        if task:
            prompt += f"## Current Task\n{task}\n\n"
        
        prompt += "Based on the current game state and strategy, what command should be executed next?\n"
        prompt += "Respond with ONLY the command to execute."
        
        return prompt

    def get_token_usage(self) -> dict:
        """Get current token usage by window."""
        return {
            name: window.current_tokens
            for name, window in self.windows.items()
        }

    def get_total_tokens(self) -> int:
        """Get total estimated tokens in context."""
        return sum(w.current_tokens for w in self.windows.values())
