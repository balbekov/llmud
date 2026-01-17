"""
Game State Manager - Tracks and analyzes game state from text output.
"""

import re
import logging
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
from enum import Enum, auto

logger = logging.getLogger(__name__)


class GamePhase(Enum):
    """Current phase of gameplay."""
    CONNECTING = auto()
    LOGIN = auto()
    CHARACTER_CREATION = auto()
    PLAYING = auto()
    COMBAT = auto()
    DEAD = auto()
    DISCONNECTED = auto()


class CombatState(Enum):
    """Combat status."""
    NONE = auto()
    INITIATING = auto()
    FIGHTING = auto()
    FLEEING = auto()
    ENDED = auto()


@dataclass
class RoomDescription:
    """Parsed room description from text."""
    title: str = ""
    description: str = ""
    items: list[str] = field(default_factory=list)
    npcs: list[str] = field(default_factory=list)
    players: list[str] = field(default_factory=list)
    exits: list[str] = field(default_factory=list)
    raw_text: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CombatInfo:
    """Combat state information."""
    in_combat: bool = False
    target: str = ""
    target_health: str = ""  # Text description like "scratched", "hurt badly"
    player_health: str = ""
    last_action: str = ""
    rounds: int = 0


@dataclass
class VisitedRoom:
    """Record of a visited room."""
    room_id: str
    name: str
    area: str
    exits: list[str]
    description: str
    visit_time: datetime = field(default_factory=datetime.now)
    visit_count: int = 1


class GameState:
    """
    Tracks game state from both GMCP and text output.
    Maintains history for context and decision making.
    """

    def __init__(self, history_size: int = 50):
        # Current state
        self.phase = GamePhase.CONNECTING
        self.combat = CombatInfo()
        self.current_room: Optional[RoomDescription] = None
        
        # History
        self._history_size = history_size
        self.output_history: deque[str] = deque(maxlen=history_size)
        self.command_history: deque[str] = deque(maxlen=history_size)
        self.room_history: deque[VisitedRoom] = deque(maxlen=history_size)
        
        # World map (room_id -> VisitedRoom)
        self.world_map: dict[str, VisitedRoom] = {}
        
        # Patterns for parsing
        self._compile_patterns()
        
        # Text buffers
        self._accumulated_text = ""

    def _compile_patterns(self) -> None:
        """Compile regex patterns for text parsing."""
        # Login prompts
        self._login_pattern = re.compile(
            r"(enter your name|what is your name|password|create a new character)",
            re.IGNORECASE
        )
        
        # Combat patterns
        self._combat_start_patterns = [
            re.compile(r"you attack", re.IGNORECASE),
            re.compile(r"attacks you", re.IGNORECASE),
            re.compile(r"you are attacked", re.IGNORECASE),
        ]
        self._combat_end_patterns = [
            re.compile(r"you killed", re.IGNORECASE),
            re.compile(r"is dead", re.IGNORECASE),
            re.compile(r"you flee", re.IGNORECASE),
            re.compile(r"combat ends", re.IGNORECASE),
        ]
        self._combat_hit_pattern = re.compile(
            r"(hit|miss|dodge|block|strike|slash|stab|punch|kick)",
            re.IGNORECASE
        )
        
        # Death patterns
        self._death_pattern = re.compile(
            r"(you have died|you are dead|your soul|axotl tank)",
            re.IGNORECASE
        )
        
        # Room patterns (basic, augmented by GMCP)
        self._exits_pattern = re.compile(
            r"obvious exits?:?\s*(.+)",
            re.IGNORECASE
        )
        
        # NPC/item patterns
        self._npc_pattern = re.compile(
            r"^([A-Z][a-zA-Z\s]+)\s+is\s+(standing|sitting|here)",
            re.MULTILINE
        )
        self._item_pattern = re.compile(
            r"^(A|An|The|Some)\s+([a-zA-Z\s]+)\s+is\s+here",
            re.MULTILINE
        )

        # Health descriptions
        self._health_patterns = {
            "perfect": 100,
            "excellent": 90,
            "fine": 80,
            "good": 70,
            "hurt": 50,
            "wounded": 40,
            "badly wounded": 30,
            "critical": 15,
            "near death": 5,
        }

    def process_text(self, text: str) -> None:
        """Process text output and update state."""
        if not text:
            return
            
        # Store in history
        self.output_history.append(text)
        self._accumulated_text += text + "\n"
        
        # Detect game phase
        self._detect_phase(text)
        
        # Parse combat state
        self._parse_combat(text)
        
        # Parse room info (supplement GMCP)
        self._parse_room_text(text)

    def record_command(self, command: str) -> None:
        """Record a sent command."""
        self.command_history.append(command)

    def update_from_gmcp(
        self, 
        room_id: str, 
        room_name: str, 
        area: str, 
        exits: list[str],
        room_text: str = ""
    ) -> None:
        """Update state from GMCP room info."""
        # Update or create room in map
        if room_id in self.world_map:
            room = self.world_map[room_id]
            room.visit_count += 1
            room.visit_time = datetime.now()
        else:
            room = VisitedRoom(
                room_id=room_id,
                name=room_name,
                area=area,
                exits=exits,
                description=room_text
            )
            self.world_map[room_id] = room
        
        # Add to history
        self.room_history.append(room)
        
        # Update current room
        self.current_room = RoomDescription(
            title=room_name,
            exits=exits,
            raw_text=room_text
        )
        
        # Transition to PLAYING if we're getting room updates
        if self.phase in (GamePhase.CONNECTING, GamePhase.LOGIN):
            self.phase = GamePhase.PLAYING

    def _detect_phase(self, text: str) -> None:
        """Detect current game phase from text."""
        text_lower = text.lower()
        
        if self._login_pattern.search(text):
            self.phase = GamePhase.LOGIN
        elif self._death_pattern.search(text):
            self.phase = GamePhase.DEAD
            self.combat.in_combat = False
        elif self.combat.in_combat:
            self.phase = GamePhase.COMBAT

    def _parse_combat(self, text: str) -> None:
        """Parse combat information from text."""
        text_lower = text.lower()
        
        # Check for combat start
        for pattern in self._combat_start_patterns:
            if pattern.search(text):
                self.combat.in_combat = True
                self.combat.rounds = 0
                self.phase = GamePhase.COMBAT
                break
        
        # Check for combat end
        for pattern in self._combat_end_patterns:
            if pattern.search(text):
                self.combat.in_combat = False
                self.combat.target = ""
                self.combat.rounds = 0
                if self.phase == GamePhase.COMBAT:
                    self.phase = GamePhase.PLAYING
                break
        
        # Count combat rounds (if we see hit/miss patterns)
        if self.combat.in_combat and self._combat_hit_pattern.search(text):
            self.combat.rounds += 1
            
        # Try to extract health descriptions
        for desc, percent in self._health_patterns.items():
            if desc in text_lower:
                # Could be player or target health
                # More sophisticated parsing would be needed for accuracy
                pass

    def _parse_room_text(self, text: str) -> None:
        """Parse room description from text."""
        # Extract exits from text (fallback if GMCP fails)
        exits_match = self._exits_pattern.search(text)
        if exits_match and self.current_room:
            exits_text = exits_match.group(1)
            exits = [e.strip() for e in re.split(r'[,\s]+', exits_text) if e.strip()]
            if not self.current_room.exits:
                self.current_room.exits = exits
        
        # Extract NPCs
        for match in self._npc_pattern.finditer(text):
            npc_name = match.group(1).strip()
            if self.current_room and npc_name not in self.current_room.npcs:
                self.current_room.npcs.append(npc_name)

    def get_recent_context(self, lines: int = 20) -> str:
        """Get recent output for context."""
        recent = list(self.output_history)[-lines:]
        return "\n".join(recent)

    def get_room_context(self) -> dict:
        """Get current room context."""
        if not self.current_room:
            return {"room": "Unknown location"}
        
        return {
            "room_name": self.current_room.title,
            "description": self.current_room.description,
            "exits": self.current_room.exits,
            "npcs": self.current_room.npcs,
            "items": self.current_room.items,
        }

    def get_combat_context(self) -> dict:
        """Get combat context."""
        return {
            "in_combat": self.combat.in_combat,
            "target": self.combat.target,
            "rounds": self.combat.rounds,
            "phase": self.phase.name,
        }

    def get_navigation_context(self) -> dict:
        """Get navigation context for mapping."""
        recent_rooms = list(self.room_history)[-5:]
        return {
            "recent_rooms": [
                {"name": r.name, "area": r.area, "exits": r.exits}
                for r in recent_rooms
            ],
            "total_rooms_discovered": len(self.world_map),
        }

    def suggest_actions(self) -> list[str]:
        """Suggest possible actions based on current state."""
        actions = []
        
        if self.phase == GamePhase.LOGIN:
            actions.extend(["Enter username", "Enter password"])
        
        elif self.phase == GamePhase.COMBAT:
            actions.extend(["Continue fighting", "Flee", "Use ability"])
        
        elif self.phase == GamePhase.PLAYING:
            if self.current_room:
                # Navigation options
                for exit_dir in self.current_room.exits:
                    actions.append(f"Go {exit_dir}")
                
                # Interaction options
                for npc in self.current_room.npcs:
                    actions.extend([
                        f"Look at {npc}",
                        f"Consider {npc}",
                        f"Talk to {npc}",
                    ])
            
            # General actions
            actions.extend([
                "Check inventory",
                "Check score",
                "Look around",
            ])
        
        elif self.phase == GamePhase.DEAD:
            actions.extend([
                "Return to life",
                "Check death location",
            ])
        
        return actions

    def get_full_state(self) -> dict:
        """Get complete game state for serialization."""
        return {
            "phase": self.phase.name,
            "combat": self.get_combat_context(),
            "room": self.get_room_context(),
            "navigation": self.get_navigation_context(),
            "suggested_actions": self.suggest_actions(),
            "recent_output": self.get_recent_context(10),
        }
