"""
GMCP Handler - Processes and manages GMCP data from the MUD.
"""

import logging
from typing import Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CharacterVitals:
    """Character health/resource stats."""
    hp: int = 0
    maxhp: int = 0
    sp: int = 0  # Command Points (CP)
    maxsp: int = 0
    
    @property
    def hp_percent(self) -> float:
        return (self.hp / self.maxhp * 100) if self.maxhp > 0 else 0
    
    @property
    def sp_percent(self) -> float:
        return (self.sp / self.maxsp * 100) if self.maxsp > 0 else 0


@dataclass
class CharacterStats:
    """Character base stats."""
    str: int = 0
    con: int = 0
    int: int = 0
    wis: int = 0
    dex: int = 0
    qui: int = 0


@dataclass
class CharacterMaxStats:
    """Character effective stats with modifiers."""
    maxstr: int = 0
    maxcon: int = 0
    maxint: int = 0
    maxwis: int = 0
    maxdex: int = 0
    maxqui: int = 0


@dataclass
class CharacterStatus:
    """Character status information."""
    level: int = 0
    money: int = 0
    bankmoney: int = 0
    guild: str = "none"
    subguild: str = "none"
    xp: int = 0
    maxxp: int = 0
    wimpy: int = 0
    wimpy_dir: str = "none"
    aim: str = ""
    quest_points: int = 0
    kills: int = 0
    deaths: int = 0
    explorer_rating: int = 0
    pk: bool = False
    inn: bool = False
    total_exp_bonus: float = 0.0


@dataclass
class CharacterInfo:
    """Complete character information."""
    name: str = ""
    fullname: str = ""
    guild: str = "none"
    vitals: CharacterVitals = field(default_factory=CharacterVitals)
    stats: CharacterStats = field(default_factory=CharacterStats)
    maxstats: CharacterMaxStats = field(default_factory=CharacterMaxStats)
    status: CharacterStatus = field(default_factory=CharacterStatus)


@dataclass 
class RoomExit:
    """Room exit information."""
    direction: str
    room_id: str


@dataclass
class RoomInfo:
    """Room information from GMCP."""
    num: str = ""
    name: str = ""
    area: str = ""
    environment: str = ""
    exits: dict[str, str] = field(default_factory=dict)
    
    def get_exit_directions(self) -> list[str]:
        """Get list of available exit directions."""
        return list(self.exits.keys())


@dataclass
class ChannelMessage:
    """Channel message information."""
    channel: str
    talker: str
    text: str
    timestamp: datetime = field(default_factory=datetime.now)


class GMCPHandler:
    """Handles GMCP data processing and state management."""

    def __init__(self):
        self.character = CharacterInfo()
        self.room = RoomInfo()
        self.channels: list[dict] = []
        self.messages: list[ChannelMessage] = []
        self._max_messages = 100
        
        # Guild-specific data
        self.guild_data: dict[str, Any] = {}
        
        # Callbacks for state changes
        self._on_vitals_change: Optional[Callable] = None
        self._on_room_change: Optional[Callable] = None
        self._on_status_change: Optional[Callable] = None
        self._on_channel_message: Optional[Callable] = None

    def on_vitals_change(self, callback: Callable) -> None:
        """Register callback for vitals changes."""
        self._on_vitals_change = callback

    def on_room_change(self, callback: Callable) -> None:
        """Register callback for room changes."""
        self._on_room_change = callback

    def on_status_change(self, callback: Callable) -> None:
        """Register callback for status changes."""
        self._on_status_change = callback

    def on_channel_message(self, callback: Callable) -> None:
        """Register callback for channel messages."""
        self._on_channel_message = callback

    def process(self, module: str, data: Any) -> None:
        """Process a GMCP message and update state."""
        logger.debug(f"Processing GMCP: {module}")
        
        # Route to appropriate handler
        if module == "Char.Name":
            self._handle_char_name(data)
        elif module == "Char.Vitals":
            self._handle_char_vitals(data)
        elif module == "Char.Stats":
            self._handle_char_stats(data)
        elif module == "Char.MaxStats":
            self._handle_char_maxstats(data)
        elif module == "Char.Status":
            self._handle_char_status(data)
        elif module == "Room.Info":
            self._handle_room_info(data)
        elif module == "Comm.Channel.List":
            self._handle_channel_list(data)
        elif module == "Comm.Channel.Text":
            self._handle_channel_text(data)
        elif module.startswith("Guild."):
            self._handle_guild_data(module, data)
        else:
            logger.debug(f"Unhandled GMCP module: {module}")

    def _handle_char_name(self, data: dict) -> None:
        """Handle Char.Name message."""
        if data:
            self.character.name = data.get("name", self.character.name)
            self.character.fullname = data.get("fullname", self.character.fullname)
            self.character.guild = data.get("guild", self.character.guild)
            logger.info(f"Character: {self.character.name} ({self.character.guild})")

    def _handle_char_vitals(self, data: dict) -> None:
        """Handle Char.Vitals message (delta updates)."""
        if data:
            if "hp" in data:
                self.character.vitals.hp = data["hp"]
            if "maxhp" in data:
                self.character.vitals.maxhp = data["maxhp"]
            if "sp" in data:
                self.character.vitals.sp = data["sp"]
            if "maxsp" in data:
                self.character.vitals.maxsp = data["maxsp"]
            
            if self._on_vitals_change:
                self._on_vitals_change(self.character.vitals)

    def _handle_char_stats(self, data: dict) -> None:
        """Handle Char.Stats message (delta updates)."""
        if data:
            for stat in ["str", "con", "int", "wis", "dex", "qui"]:
                if stat in data:
                    setattr(self.character.stats, stat, data[stat])

    def _handle_char_maxstats(self, data: dict) -> None:
        """Handle Char.MaxStats message (delta updates)."""
        if data:
            for stat in ["maxstr", "maxcon", "maxint", "maxwis", "maxdex", "maxqui"]:
                if stat in data:
                    setattr(self.character.maxstats, stat, data[stat])

    def _handle_char_status(self, data: dict) -> None:
        """Handle Char.Status message (delta updates)."""
        if data:
            status = self.character.status
            if "level" in data:
                status.level = data["level"]
            if "money" in data:
                status.money = data["money"]
            if "bankmoney" in data:
                status.bankmoney = data["bankmoney"]
            if "guild" in data:
                status.guild = data["guild"]
            if "subguild" in data:
                status.subguild = data["subguild"]
            if "xp" in data:
                status.xp = data["xp"]
            if "maxxp" in data:
                status.maxxp = data["maxxp"]
            if "wimpy" in data:
                status.wimpy = data["wimpy"]
            if "wimpy_dir" in data:
                status.wimpy_dir = data["wimpy_dir"]
            if "quest_points" in data:
                status.quest_points = data["quest_points"]
            if "kills" in data:
                status.kills = data["kills"]
            if "deaths" in data:
                status.deaths = data["deaths"]
            if "explorer_rating" in data:
                status.explorer_rating = data["explorer_rating"]
            if "pk" in data:
                status.pk = bool(data["pk"])
            if "inn" in data:
                status.inn = bool(data["inn"])
            if "total_exp_bonus" in data:
                status.total_exp_bonus = float(data["total_exp_bonus"])
            
            if self._on_status_change:
                self._on_status_change(status)

    def _handle_room_info(self, data: dict) -> None:
        """Handle Room.Info message."""
        if data:
            old_room = self.room.num
            self.room.num = data.get("num", "")
            self.room.name = data.get("name", "")
            self.room.area = data.get("area", "")
            self.room.environment = data.get("environment", "")
            self.room.exits = data.get("exits", {})
            
            logger.info(f"Room: {self.room.name} ({self.room.area})")
            
            if self.room.num != old_room and self._on_room_change:
                self._on_room_change(self.room)

    def _handle_channel_list(self, data: list) -> None:
        """Handle Comm.Channel.List message."""
        if data:
            self.channels = data
            logger.debug(f"Channels loaded: {len(self.channels)}")

    def _handle_channel_text(self, data: dict) -> None:
        """Handle Comm.Channel.Text message."""
        if data:
            message = ChannelMessage(
                channel=data.get("channel", ""),
                talker=data.get("talker", ""),
                text=data.get("text", ""),
            )
            self.messages.append(message)
            
            # Trim old messages
            if len(self.messages) > self._max_messages:
                self.messages = self.messages[-self._max_messages:]
            
            if self._on_channel_message:
                self._on_channel_message(message)

    def _handle_guild_data(self, module: str, data: Any) -> None:
        """Handle guild-specific GMCP messages."""
        # Store guild data by submodule
        submodule = module[6:]  # Remove "Guild." prefix
        self.guild_data[submodule] = data
        logger.debug(f"Guild data: {submodule}")

    def get_state_summary(self) -> dict:
        """Get a summary of current game state."""
        return {
            "character": {
                "name": self.character.name,
                "guild": self.character.guild,
                "level": self.character.status.level,
                "hp": f"{self.character.vitals.hp}/{self.character.vitals.maxhp}",
                "cp": f"{self.character.vitals.sp}/{self.character.vitals.maxsp}",
                "hp_percent": round(self.character.vitals.hp_percent, 1),
                "cp_percent": round(self.character.vitals.sp_percent, 1),
                "money": self.character.status.money,
                "bank": self.character.status.bankmoney,
                "wimpy": self.character.status.wimpy,
            },
            "room": {
                "name": self.room.name,
                "area": self.room.area,
                "environment": self.room.environment,
                "exits": self.room.get_exit_directions(),
            },
            "stats": {
                "str": self.character.maxstats.maxstr or self.character.stats.str,
                "con": self.character.maxstats.maxcon or self.character.stats.con,
                "int": self.character.maxstats.maxint or self.character.stats.int,
                "wis": self.character.maxstats.maxwis or self.character.stats.wis,
                "dex": self.character.maxstats.maxdex or self.character.stats.dex,
                "qui": self.character.maxstats.maxqui or self.character.stats.qui,
            }
        }
