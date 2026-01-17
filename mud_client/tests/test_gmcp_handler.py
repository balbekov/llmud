"""Tests for the GMCP Handler - Attribute synchronization."""

import pytest
from pathlib import Path
import sys

# Add the parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from llmud.gmcp_handler import (
    GMCPHandler,
    CharacterVitals,
    CharacterStats,
    CharacterMaxStats,
    CharacterStatus,
    CharacterInfo,
    RoomInfo,
    ChannelMessage,
)


class TestCharacterVitals:
    """Tests for CharacterVitals dataclass."""
    
    def test_default_values(self):
        """Test default vitals are zero."""
        vitals = CharacterVitals()
        assert vitals.hp == 0
        assert vitals.maxhp == 0
        assert vitals.sp == 0
        assert vitals.maxsp == 0
    
    def test_hp_percent_calculation(self):
        """Test HP percentage calculation."""
        vitals = CharacterVitals(hp=50, maxhp=100, sp=75, maxsp=150)
        assert vitals.hp_percent == 50.0
        assert vitals.sp_percent == 50.0
    
    def test_hp_percent_zero_max(self):
        """Test HP percentage with zero max (avoid division by zero)."""
        vitals = CharacterVitals(hp=50, maxhp=0)
        assert vitals.hp_percent == 0
    
    def test_sp_percent_zero_max(self):
        """Test SP percentage with zero max (avoid division by zero)."""
        vitals = CharacterVitals(sp=50, maxsp=0)
        assert vitals.sp_percent == 0


class TestCharacterStats:
    """Tests for CharacterStats dataclass."""
    
    def test_default_values(self):
        """Test default stats are zero."""
        stats = CharacterStats()
        assert stats.str == 0
        assert stats.con == 0
        assert stats.int == 0
        assert stats.wis == 0
        assert stats.dex == 0
        assert stats.qui == 0
    
    def test_custom_values(self):
        """Test setting custom stat values."""
        stats = CharacterStats(str=15, con=12, int=10, wis=8, dex=14, qui=11)
        assert stats.str == 15
        assert stats.con == 12
        assert stats.int == 10
        assert stats.wis == 8
        assert stats.dex == 14
        assert stats.qui == 11


class TestCharacterMaxStats:
    """Tests for CharacterMaxStats dataclass."""
    
    def test_default_values(self):
        """Test default max stats are zero."""
        maxstats = CharacterMaxStats()
        assert maxstats.maxstr == 0
        assert maxstats.maxcon == 0
        assert maxstats.maxint == 0
        assert maxstats.maxwis == 0
        assert maxstats.maxdex == 0
        assert maxstats.maxqui == 0


class TestCharacterStatus:
    """Tests for CharacterStatus dataclass."""
    
    def test_default_values(self):
        """Test default status values."""
        status = CharacterStatus()
        assert status.level == 0
        assert status.money == 0
        assert status.bankmoney == 0
        assert status.guild == "none"
        assert status.subguild == "none"
        assert status.xp == 0
        assert status.maxxp == 0
        assert status.wimpy == 0
        assert status.wimpy_dir == "none"
        assert status.aim == ""
        assert status.quest_points == 0
        assert status.kills == 0
        assert status.deaths == 0
        assert status.explorer_rating == 0
        assert status.pk is False
        assert status.inn is False
        assert status.total_exp_bonus == 0.0
    
    def test_wimpy_setting(self):
        """Test wimpy attribute can be set."""
        status = CharacterStatus(wimpy=20, wimpy_dir="south")
        assert status.wimpy == 20
        assert status.wimpy_dir == "south"


class TestRoomInfo:
    """Tests for RoomInfo dataclass."""
    
    def test_default_values(self):
        """Test default room info values."""
        room = RoomInfo()
        assert room.num == ""
        assert room.name == ""
        assert room.area == ""
        assert room.environment == ""
        assert room.exits == {}
    
    def test_get_exit_directions(self):
        """Test getting exit directions."""
        room = RoomInfo(
            num="room1",
            name="Test Room",
            exits={"n": "room2", "s": "room3", "e": "room4"}
        )
        directions = room.get_exit_directions()
        assert set(directions) == {"n", "s", "e"}


class TestGMCPHandler:
    """Tests for GMCPHandler class."""
    
    def test_create_handler(self):
        """Test creating a GMCP handler."""
        handler = GMCPHandler()
        assert handler.character is not None
        assert handler.room is not None
        assert handler.channels == []
        assert handler.messages == []
    
    def test_process_char_name(self):
        """Test processing Char.Name GMCP message."""
        handler = GMCPHandler()
        handler.process("Char.Name", {
            "name": "TestPlayer",
            "fullname": "Test Player the Brave",
            "guild": "warrior"
        })
        
        assert handler.character.name == "TestPlayer"
        assert handler.character.fullname == "Test Player the Brave"
        assert handler.character.guild == "warrior"
    
    def test_process_char_vitals(self):
        """Test processing Char.Vitals GMCP message."""
        handler = GMCPHandler()
        
        # Initial full vitals update
        handler.process("Char.Vitals", {
            "hp": 100,
            "maxhp": 150,
            "sp": 75,
            "maxsp": 100
        })
        
        assert handler.character.vitals.hp == 100
        assert handler.character.vitals.maxhp == 150
        assert handler.character.vitals.sp == 75
        assert handler.character.vitals.maxsp == 100
    
    def test_process_char_vitals_delta(self):
        """Test processing Char.Vitals delta update (partial)."""
        handler = GMCPHandler()
        
        # Set initial values
        handler.process("Char.Vitals", {
            "hp": 100,
            "maxhp": 150,
            "sp": 75,
            "maxsp": 100
        })
        
        # Delta update (only HP changed)
        handler.process("Char.Vitals", {"hp": 80})
        
        assert handler.character.vitals.hp == 80
        assert handler.character.vitals.maxhp == 150  # Unchanged
        assert handler.character.vitals.sp == 75  # Unchanged
    
    def test_process_char_stats(self):
        """Test processing Char.Stats GMCP message."""
        handler = GMCPHandler()
        handler.process("Char.Stats", {
            "str": 15,
            "con": 12,
            "int": 10,
            "wis": 8,
            "dex": 14,
            "qui": 11
        })
        
        assert handler.character.stats.str == 15
        assert handler.character.stats.con == 12
        assert handler.character.stats.int == 10
        assert handler.character.stats.wis == 8
        assert handler.character.stats.dex == 14
        assert handler.character.stats.qui == 11
    
    def test_process_char_maxstats(self):
        """Test processing Char.MaxStats GMCP message."""
        handler = GMCPHandler()
        handler.process("Char.MaxStats", {
            "maxstr": 18,
            "maxcon": 16,
            "maxint": 14,
            "maxwis": 12,
            "maxdex": 17,
            "maxqui": 15
        })
        
        assert handler.character.maxstats.maxstr == 18
        assert handler.character.maxstats.maxcon == 16
        assert handler.character.maxstats.maxint == 14
        assert handler.character.maxstats.maxwis == 12
        assert handler.character.maxstats.maxdex == 17
        assert handler.character.maxstats.maxqui == 15
    
    def test_process_char_status(self):
        """Test processing Char.Status GMCP message."""
        handler = GMCPHandler()
        handler.process("Char.Status", {
            "level": 10,
            "money": 1000,
            "bankmoney": 5000,
            "guild": "warrior",
            "subguild": "knight",
            "xp": 25000,
            "maxxp": 50000,
            "wimpy": 20,
            "wimpy_dir": "south",
            "quest_points": 15,
            "kills": 100,
            "deaths": 5,
            "explorer_rating": 50,
            "pk": True,
            "inn": False,
            "total_exp_bonus": 1.5
        })
        
        status = handler.character.status
        assert status.level == 10
        assert status.money == 1000
        assert status.bankmoney == 5000
        assert status.guild == "warrior"
        assert status.subguild == "knight"
        assert status.xp == 25000
        assert status.maxxp == 50000
        assert status.wimpy == 20
        assert status.wimpy_dir == "south"
        assert status.quest_points == 15
        assert status.kills == 100
        assert status.deaths == 5
        assert status.explorer_rating == 50
        assert status.pk is True
        assert status.inn is False
        assert status.total_exp_bonus == 1.5
    
    def test_process_char_status_delta(self):
        """Test processing Char.Status delta update (partial)."""
        handler = GMCPHandler()
        
        # Initial status
        handler.process("Char.Status", {
            "level": 10,
            "wimpy": 20,
            "money": 1000
        })
        
        # Delta update (wimpy changed)
        handler.process("Char.Status", {"wimpy": 30})
        
        assert handler.character.status.wimpy == 30
        assert handler.character.status.level == 10  # Unchanged
        assert handler.character.status.money == 1000  # Unchanged
    
    def test_process_room_info(self):
        """Test processing Room.Info GMCP message."""
        handler = GMCPHandler()
        handler.process("Room.Info", {
            "num": "room123",
            "name": "The Town Square",
            "area": "Caladan",
            "environment": "outdoor",
            "exits": {"n": "room124", "s": "room122", "e": "room125"}
        })
        
        assert handler.room.num == "room123"
        assert handler.room.name == "The Town Square"
        assert handler.room.area == "Caladan"
        assert handler.room.environment == "outdoor"
        assert handler.room.exits == {"n": "room124", "s": "room122", "e": "room125"}
    
    def test_process_channel_list(self):
        """Test processing Comm.Channel.List GMCP message."""
        handler = GMCPHandler()
        handler.process("Comm.Channel.List", [
            {"name": "chat", "caption": "Chat"},
            {"name": "newbie", "caption": "Newbie"},
        ])
        
        assert len(handler.channels) == 2
    
    def test_process_channel_text(self):
        """Test processing Comm.Channel.Text GMCP message."""
        handler = GMCPHandler()
        handler.process("Comm.Channel.Text", {
            "channel": "chat",
            "talker": "TestPlayer",
            "text": "Hello everyone!"
        })
        
        assert len(handler.messages) == 1
        msg = handler.messages[0]
        assert msg.channel == "chat"
        assert msg.talker == "TestPlayer"
        assert msg.text == "Hello everyone!"
    
    def test_process_guild_data(self):
        """Test processing Guild.* GMCP messages."""
        handler = GMCPHandler()
        handler.process("Guild.Info", {"rank": 5, "title": "Knight"})
        
        assert "Info" in handler.guild_data
        assert handler.guild_data["Info"]["rank"] == 5
    
    def test_vitals_change_callback(self):
        """Test vitals change callback is invoked."""
        handler = GMCPHandler()
        callback_data = {}
        
        def on_vitals(vitals):
            callback_data["hp"] = vitals.hp
            callback_data["sp"] = vitals.sp
        
        handler.on_vitals_change(on_vitals)
        handler.process("Char.Vitals", {"hp": 100, "sp": 50})
        
        assert callback_data["hp"] == 100
        assert callback_data["sp"] == 50
    
    def test_room_change_callback(self):
        """Test room change callback is invoked."""
        handler = GMCPHandler()
        callback_data = {}
        
        def on_room(room):
            callback_data["num"] = room.num
            callback_data["name"] = room.name
        
        handler.on_room_change(on_room)
        handler.process("Room.Info", {"num": "room1", "name": "Test Room"})
        
        assert callback_data["num"] == "room1"
        assert callback_data["name"] == "Test Room"
    
    def test_room_change_callback_not_invoked_same_room(self):
        """Test room change callback not invoked for same room."""
        handler = GMCPHandler()
        callback_count = {"count": 0}
        
        def on_room(room):
            callback_count["count"] += 1
        
        handler.on_room_change(on_room)
        
        # First room visit
        handler.process("Room.Info", {"num": "room1", "name": "Test Room"})
        assert callback_count["count"] == 1
        
        # Same room again (should not invoke)
        handler.process("Room.Info", {"num": "room1", "name": "Test Room"})
        assert callback_count["count"] == 1  # Still 1
        
        # Different room (should invoke)
        handler.process("Room.Info", {"num": "room2", "name": "Other Room"})
        assert callback_count["count"] == 2
    
    def test_status_change_callback(self):
        """Test status change callback is invoked."""
        handler = GMCPHandler()
        callback_data = {}
        
        def on_status(status):
            callback_data["wimpy"] = status.wimpy
            callback_data["level"] = status.level
        
        handler.on_status_change(on_status)
        handler.process("Char.Status", {"wimpy": 25, "level": 15})
        
        assert callback_data["wimpy"] == 25
        assert callback_data["level"] == 15
    
    def test_channel_message_callback(self):
        """Test channel message callback is invoked."""
        handler = GMCPHandler()
        callback_data = {}
        
        def on_message(msg):
            callback_data["channel"] = msg.channel
            callback_data["text"] = msg.text
        
        handler.on_channel_message(on_message)
        handler.process("Comm.Channel.Text", {
            "channel": "chat",
            "talker": "Player",
            "text": "Hello!"
        })
        
        assert callback_data["channel"] == "chat"
        assert callback_data["text"] == "Hello!"
    
    def test_message_history_limit(self):
        """Test message history is capped at max_messages."""
        handler = GMCPHandler()
        handler._max_messages = 5
        
        # Add more messages than the limit
        for i in range(10):
            handler.process("Comm.Channel.Text", {
                "channel": "chat",
                "talker": "Player",
                "text": f"Message {i}"
            })
        
        assert len(handler.messages) == 5
        # Should have the last 5 messages
        assert handler.messages[0].text == "Message 5"
        assert handler.messages[-1].text == "Message 9"
    
    def test_get_state_summary(self):
        """Test getting a state summary."""
        handler = GMCPHandler()
        
        # Set up some state
        handler.process("Char.Name", {"name": "TestPlayer", "guild": "warrior"})
        handler.process("Char.Vitals", {"hp": 100, "maxhp": 150, "sp": 50, "maxsp": 100})
        handler.process("Char.Status", {"level": 10, "money": 1000, "wimpy": 20})
        handler.process("Room.Info", {
            "num": "room1",
            "name": "Town Square",
            "area": "Caladan",
            "environment": "outdoor",
            "exits": {"n": "room2"}
        })
        handler.process("Char.MaxStats", {"maxstr": 15, "maxcon": 12})
        
        summary = handler.get_state_summary()
        
        assert summary["character"]["name"] == "TestPlayer"
        assert summary["character"]["guild"] == "warrior"
        assert summary["character"]["level"] == 10
        assert summary["character"]["hp"] == "100/150"
        assert summary["character"]["cp"] == "50/100"
        assert summary["character"]["wimpy"] == 20
        assert summary["room"]["name"] == "Town Square"
        assert summary["room"]["area"] == "Caladan"
        assert "n" in summary["room"]["exits"]
        assert summary["stats"]["str"] == 15
        assert summary["stats"]["con"] == 12
    
    def test_handle_empty_data(self):
        """Test handling empty/None data gracefully."""
        handler = GMCPHandler()
        
        # Should not raise
        handler.process("Char.Vitals", None)
        handler.process("Char.Vitals", {})
        handler.process("Room.Info", None)
        handler.process("Room.Info", {})
        
        # State should remain default
        assert handler.character.vitals.hp == 0
        assert handler.room.num == ""
    
    def test_unhandled_module(self):
        """Test unhandled GMCP modules are logged but don't raise."""
        handler = GMCPHandler()
        
        # Should not raise
        handler.process("Unknown.Module", {"data": "test"})


class TestWimpyAttributeSync:
    """Tests specifically for wimpy attribute synchronization."""
    
    def test_wimpy_initial_state(self):
        """Test wimpy starts at default value."""
        handler = GMCPHandler()
        assert handler.character.status.wimpy == 0
        assert handler.character.status.wimpy_dir == "none"
    
    def test_wimpy_update_from_gmcp(self):
        """Test wimpy is updated from GMCP message."""
        handler = GMCPHandler()
        
        handler.process("Char.Status", {"wimpy": 25})
        assert handler.character.status.wimpy == 25
        
        handler.process("Char.Status", {"wimpy_dir": "north"})
        assert handler.character.status.wimpy_dir == "north"
    
    def test_wimpy_combined_update(self):
        """Test wimpy and wimpy_dir updated together."""
        handler = GMCPHandler()
        
        handler.process("Char.Status", {
            "wimpy": 30,
            "wimpy_dir": "south"
        })
        
        assert handler.character.status.wimpy == 30
        assert handler.character.status.wimpy_dir == "south"
    
    def test_wimpy_in_state_summary(self):
        """Test wimpy is included in state summary."""
        handler = GMCPHandler()
        handler.process("Char.Status", {"wimpy": 35})
        
        summary = handler.get_state_summary()
        assert summary["character"]["wimpy"] == 35
    
    def test_wimpy_change_triggers_callback(self):
        """Test wimpy change triggers status callback."""
        handler = GMCPHandler()
        callback_data = {}
        
        def on_status(status):
            callback_data["wimpy"] = status.wimpy
            callback_data["wimpy_dir"] = status.wimpy_dir
        
        handler.on_status_change(on_status)
        handler.process("Char.Status", {"wimpy": 40, "wimpy_dir": "east"})
        
        assert callback_data["wimpy"] == 40
        assert callback_data["wimpy_dir"] == "east"


class TestVitalsAttributeSync:
    """Tests specifically for vitals (HP/CP) attribute synchronization."""
    
    def test_vitals_initial_state(self):
        """Test vitals start at default values."""
        handler = GMCPHandler()
        assert handler.character.vitals.hp == 0
        assert handler.character.vitals.maxhp == 0
        assert handler.character.vitals.sp == 0
        assert handler.character.vitals.maxsp == 0
    
    def test_vitals_full_update(self):
        """Test full vitals update from GMCP."""
        handler = GMCPHandler()
        
        handler.process("Char.Vitals", {
            "hp": 95,
            "maxhp": 120,
            "sp": 80,
            "maxsp": 100
        })
        
        assert handler.character.vitals.hp == 95
        assert handler.character.vitals.maxhp == 120
        assert handler.character.vitals.sp == 80
        assert handler.character.vitals.maxsp == 100
    
    def test_vitals_delta_hp_only(self):
        """Test delta update with only HP changed."""
        handler = GMCPHandler()
        
        # Initial state
        handler.process("Char.Vitals", {
            "hp": 100,
            "maxhp": 100,
            "sp": 50,
            "maxsp": 50
        })
        
        # Damage taken - only HP changed
        handler.process("Char.Vitals", {"hp": 75})
        
        assert handler.character.vitals.hp == 75
        assert handler.character.vitals.maxhp == 100  # Unchanged
        assert handler.character.vitals.sp == 50  # Unchanged
        assert handler.character.vitals.maxsp == 50  # Unchanged
    
    def test_vitals_delta_sp_only(self):
        """Test delta update with only SP (Command Points) changed."""
        handler = GMCPHandler()
        
        # Initial state
        handler.process("Char.Vitals", {
            "hp": 100,
            "maxhp": 100,
            "sp": 50,
            "maxsp": 50
        })
        
        # Ability used - only SP changed
        handler.process("Char.Vitals", {"sp": 30})
        
        assert handler.character.vitals.hp == 100  # Unchanged
        assert handler.character.vitals.sp == 30
    
    def test_vitals_percentage_calculations(self):
        """Test HP/SP percentage calculations after updates."""
        handler = GMCPHandler()
        
        handler.process("Char.Vitals", {
            "hp": 75,
            "maxhp": 150,
            "sp": 40,
            "maxsp": 80
        })
        
        assert handler.character.vitals.hp_percent == 50.0
        assert handler.character.vitals.sp_percent == 50.0
    
    def test_vitals_in_state_summary(self):
        """Test vitals are included in state summary."""
        handler = GMCPHandler()
        
        handler.process("Char.Vitals", {
            "hp": 80,
            "maxhp": 100,
            "sp": 60,
            "maxsp": 80
        })
        
        summary = handler.get_state_summary()
        assert summary["character"]["hp"] == "80/100"
        assert summary["character"]["cp"] == "60/80"
        assert summary["character"]["hp_percent"] == 80.0
        assert summary["character"]["cp_percent"] == 75.0
    
    def test_vitals_callback_on_update(self):
        """Test vitals callback is triggered on update."""
        handler = GMCPHandler()
        callback_calls = []
        
        def on_vitals(vitals):
            callback_calls.append({
                "hp": vitals.hp,
                "maxhp": vitals.maxhp,
                "sp": vitals.sp,
                "maxsp": vitals.maxsp
            })
        
        handler.on_vitals_change(on_vitals)
        
        # First update
        handler.process("Char.Vitals", {"hp": 100, "maxhp": 100})
        assert len(callback_calls) == 1
        assert callback_calls[0]["hp"] == 100
        
        # Delta update
        handler.process("Char.Vitals", {"hp": 90})
        assert len(callback_calls) == 2
        assert callback_calls[1]["hp"] == 90


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
