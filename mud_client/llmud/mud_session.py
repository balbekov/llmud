"""
MUD Session - Main orchestrator for AI-driven MUD gameplay.
"""

import asyncio
import logging
import json
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .telnet_client import TelnetClient
from .gmcp_handler import GMCPHandler
from .game_state import GameState, GamePhase
from .context_manager import ContextManager
from .llm_agent import LLMAgent, LLMResponse
from .map_agent import MapAgent

logger = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    """Configuration for a MUD session."""
    host: str = "dunemud.net"
    port: int = 6789
    username: str = ""
    password: str = ""
    strategy_path: str = ""
    llm_provider: str = "anthropic"
    llm_api_key: str = ""
    llm_model: str = ""
    auto_play: bool = False
    command_delay: float = 2.0  # Seconds between AI commands
    # Mapping configuration
    map_enabled: bool = True
    map_path: str = ""  # Path to save/load map (JSON)
    map_auto_save: bool = True
    map_images_dir: str = ""  # Directory for room images
    map_llm_analysis: bool = False  # Use LLM to analyze room text


@dataclass
class SessionEvent:
    """Event from the session."""
    type: str  # "text", "gmcp", "command", "state_change"
    data: Any
    timestamp: datetime = field(default_factory=datetime.now)


class MUDSession:
    """
    Main session manager that orchestrates:
    - Telnet connection
    - GMCP processing
    - Game state tracking
    - LLM decision making
    - Event callbacks for UI
    """

    def __init__(self, config: SessionConfig):
        self.config = config
        
        # Core components
        self.telnet = TelnetClient(config.host, config.port)
        self.gmcp = GMCPHandler()
        self.state = GameState()
        self.context = ContextManager(strategy_path=config.strategy_path)
        
        # LLM agent (lazy loaded)
        self._agent: Optional[LLMAgent] = None
        
        # Map agent (initialized if mapping enabled)
        self.map_agent: Optional[MapAgent] = None
        if config.map_enabled:
            self.map_agent = MapAgent(
                provider=config.llm_provider,
                api_key=config.llm_api_key or None,
                model=config.llm_model or None,
                map_path=config.map_path or None,
                auto_save=config.map_auto_save,
                images_dir=config.map_images_dir or None,
            )
        
        # Session state
        self._running = False
        self._auto_mode = config.auto_play
        self._paused = False
        
        # Event callbacks
        self._event_callbacks: list[Callable[[SessionEvent], Any]] = []
        
        # Command queue for manual commands
        self._command_queue: asyncio.Queue[str] = asyncio.Queue()
        
        # Track last movement direction for mapping
        self._last_movement_direction: Optional[str] = None
        
        # Register internal callbacks
        self._setup_callbacks()

    def _setup_callbacks(self) -> None:
        """Set up internal callbacks."""
        # Text callback
        self.telnet.on_text(self._on_text)
        
        # GMCP callback
        self.telnet.on_gmcp(self._on_gmcp)
        
        # GMCP state callbacks
        self.gmcp.on_vitals_change(self._on_vitals_change)
        self.gmcp.on_room_change(self._on_room_change)
        self.gmcp.on_channel_message(self._on_channel_message)

    def _get_agent(self) -> LLMAgent:
        """Lazy load the LLM agent."""
        if self._agent is None:
            self._agent = LLMAgent(
                provider=self.config.llm_provider,
                api_key=self.config.llm_api_key or None,
                model=self.config.llm_model or None,
            )
        return self._agent

    def on_event(self, callback: Callable[[SessionEvent], Any]) -> None:
        """Register callback for session events."""
        self._event_callbacks.append(callback)

    def _emit_event(self, event_type: str, data: Any) -> None:
        """Emit an event to all callbacks."""
        event = SessionEvent(type=event_type, data=data)
        for callback in self._event_callbacks:
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

    async def _on_text(self, text: str) -> None:
        """Handle received text."""
        # Update game state
        self.state.process_text(text)
        
        # Update context
        self.context.add_output(text)
        
        # Emit event
        self._emit_event("text", {
            "text": text,
            "phase": self.state.phase.name,
        })

    async def _on_gmcp(self, module: str, data: Any) -> None:
        """Handle GMCP message."""
        # Process through handler
        self.gmcp.process(module, data)
        
        # Emit event
        self._emit_event("gmcp", {
            "module": module,
            "data": data,
        })

    def _on_vitals_change(self, vitals) -> None:
        """Handle vitals change."""
        # Update context
        state_summary = self.gmcp.get_state_summary()
        self.context.update_game_state(state_summary)
        
        # Emit state change
        self._emit_event("state_change", {
            "type": "vitals",
            "data": state_summary,
        })

    def _on_room_change(self, room) -> None:
        """Handle room change."""
        # Update context
        room_data = {
            "name": room.name,
            "area": room.area,
            "environment": room.environment,
            "exits": room.get_exit_directions(),
        }
        self.context.update_current_room(room_data)
        
        # Update game state
        self.state.update_from_gmcp(
            room_id=room.num,
            room_name=room.name,
            area=room.area,
            exits=room.get_exit_directions(),
        )
        
        # Update world map in context
        self.context.update_world_map(self.state.world_map)
        
        # Update map agent
        if self.map_agent:
            # Record movement if we have a previous direction
            if self._last_movement_direction:
                self.map_agent.record_movement(
                    self._last_movement_direction,
                    room.num
                )
                self._last_movement_direction = None
            
            # Update from GMCP data
            self.map_agent.update_from_gmcp(
                room_id=room.num,
                room_name=room.name,
                area=room.area,
                environment=room.environment,
                exits=room.exits,  # This is a dict from GMCP
            )
            
            # Emit map update event
            self._emit_event("map_update", {
                "room_id": room.num,
                "room_name": room.name,
                "map_stats": self.map_agent.get_map_stats(),
            })
        
        # Emit state change
        self._emit_event("state_change", {
            "type": "room",
            "data": room_data,
        })

    def _on_channel_message(self, message) -> None:
        """Handle channel message."""
        self._emit_event("chat", {
            "channel": message.channel,
            "talker": message.talker,
            "text": message.text,
        })

    async def connect(self) -> bool:
        """Connect to the MUD."""
        logger.info(f"Connecting to {self.config.host}:{self.config.port}")
        
        success = await self.telnet.connect()
        if success:
            self._emit_event("connected", {"host": self.config.host})
        return success

    async def disconnect(self) -> None:
        """Disconnect from the MUD."""
        self._running = False
        await self.telnet.disconnect()
        self._emit_event("disconnected", {})

    async def send_command(self, command: str) -> None:
        """Send a command to the MUD."""
        if not command:
            return
        
        # Record command
        self.state.record_command(command)
        
        # Track movement direction for mapping
        movement_commands = {
            "n", "s", "e", "w", "ne", "nw", "se", "sw", "u", "d",
            "north", "south", "east", "west", "up", "down",
            "northeast", "northwest", "southeast", "southwest",
            "enter", "out",
        }
        cmd_lower = command.lower().strip()
        if cmd_lower in movement_commands:
            # Normalize to short form
            direction_map = {
                "north": "n", "south": "s", "east": "e", "west": "w",
                "up": "u", "down": "d",
                "northeast": "ne", "northwest": "nw",
                "southeast": "se", "southwest": "sw",
            }
            self._last_movement_direction = direction_map.get(cmd_lower, cmd_lower)
        
        # Send to MUD
        await self.telnet.send(command)
        
        # Emit event
        self._emit_event("command", {
            "command": command,
            "source": "manual",
        })

    async def queue_command(self, command: str) -> None:
        """Queue a command for sending."""
        await self._command_queue.put(command)

    async def login(self, username: str = "", password: str = "") -> None:
        """Attempt to login to the MUD."""
        username = username or self.config.username
        password = password or self.config.password
        
        if username:
            await asyncio.sleep(1)
            await self.send_command(username)
        
        if password:
            await asyncio.sleep(0.5)
            await self.send_command(password)

    async def _ai_decide_and_act(self) -> Optional[LLMResponse]:
        """Let the AI decide and execute the next action."""
        if self._paused or not self._auto_mode:
            return None
        
        # Check if we should act based on game state
        if self.state.phase == GamePhase.LOGIN:
            # Handle login separately
            return None
        
        try:
            agent = self._get_agent()
            
            # Build prompts
            system_prompt = self.context.get_system_prompt()
            user_prompt = self.context.build_user_prompt()
            
            # Get AI decision
            response = await agent.get_command(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            
            if response.command:
                # Execute command
                await self.send_command(response.command)
                
                # Emit event
                self._emit_event("ai_action", {
                    "command": response.command,
                    "model": response.model,
                    "tokens": response.tokens_used,
                })
            
            return response
            
        except Exception as e:
            logger.error(f"AI decision error: {e}")
            self._emit_event("error", {"message": str(e)})
            return None

    async def run(self) -> None:
        """Main session loop."""
        self._running = True
        
        logger.info("Starting session loop")
        
        while self._running:
            try:
                # Receive data
                text = await self.telnet.receive()
                
                # Process manual command queue
                try:
                    command = self._command_queue.get_nowait()
                    await self.send_command(command)
                except asyncio.QueueEmpty:
                    pass
                
                # AI auto-play
                if self._auto_mode and not self._paused:
                    # Check if we should make a decision
                    # (Add delays and conditions as needed)
                    await asyncio.sleep(self.config.command_delay)
                    await self._ai_decide_and_act()
                
            except Exception as e:
                logger.error(f"Session loop error: {e}")
                if not self.telnet.connected:
                    self._running = False
                    self._emit_event("disconnected", {"error": str(e)})

    def set_auto_mode(self, enabled: bool) -> None:
        """Enable/disable auto-play mode."""
        self._auto_mode = enabled
        self._emit_event("mode_change", {"auto": enabled})

    def pause(self) -> None:
        """Pause auto-play."""
        self._paused = True
        self._emit_event("paused", {})

    def resume(self) -> None:
        """Resume auto-play."""
        self._paused = False
        self._emit_event("resumed", {})

    def get_state(self) -> dict:
        """Get current session state."""
        state = {
            "connected": self.telnet.connected,
            "phase": self.state.phase.name,
            "auto_mode": self._auto_mode,
            "paused": self._paused,
            "character": self.gmcp.get_state_summary(),
            "room": self.state.get_room_context(),
            "combat": self.state.get_combat_context(),
            "navigation": self.state.get_navigation_context(),
            "world_map_size": len(self.state.world_map),
        }
        
        # Add map agent info if available
        if self.map_agent:
            state["map"] = self.map_agent.get_map_stats()
            state["current_room_info"] = self.map_agent.get_current_room_info()
            state["adjacent_rooms"] = self.map_agent.get_adjacent_rooms_info()
        
        return state

    def get_action_buttons(self) -> list[dict]:
        """Get current action buttons."""
        room = self.state.current_room
        buttons = []
        
        # Navigation
        if room:
            for exit_dir in room.exits:
                buttons.append({
                    "label": exit_dir.upper(),
                    "command": exit_dir,
                    "type": "navigation",
                })
            
            # NPC actions
            for npc in room.npcs[:3]:
                buttons.append({
                    "label": f"Consider {npc}",
                    "command": f"consider {npc}",
                    "type": "combat",
                })
        
        # Standard actions
        buttons.extend([
            {"label": "Look", "command": "look", "type": "info"},
            {"label": "Score", "command": "score", "type": "info"},
            {"label": "Inventory", "command": "i", "type": "info"},
        ])
        
        # Combat actions
        if self.state.combat.in_combat:
            buttons.extend([
                {"label": "Flee", "command": "flee", "type": "combat"},
            ])
        
        return buttons

    def get_map_data(self) -> dict:
        """Get world map data for visualization."""
        if self.map_agent:
            return self.map_agent.get_map_data_for_visualization()
        
        # Fallback to basic game state map
        rooms = []
        for room_id, room in self.state.world_map.items():
            rooms.append({
                "id": room_id,
                "name": room.name,
                "area": room.area,
                "exits": room.exits,
                "visits": room.visit_count,
            })
        return {"rooms": rooms, "edges": [], "current_room_id": None}
    
    # ==================== Map Operations ====================
    
    def get_route_to(self, destination: str) -> Optional[dict]:
        """Get route to a destination room, name, or tag."""
        if not self.map_agent:
            return None
        return self.map_agent.get_route_to(destination)
    
    def save_map(self, path: Optional[str] = None) -> bool:
        """Save the current map to disk."""
        if not self.map_agent:
            return False
        return self.map_agent.save_map(path)
    
    def load_map(self, path: Optional[str] = None) -> bool:
        """Load a map from disk."""
        if not self.map_agent:
            return False
        return self.map_agent.load_map(path)
    
    async def analyze_current_room(self) -> list:
        """Use LLM to analyze the current room text and update map."""
        if not self.map_agent:
            return []
        
        if not self.config.map_llm_analysis:
            return []
        
        # Get recent room text from output history
        room_text = self.state.get_recent_context(20)
        
        return await self.map_agent.analyze_room_text(room_text)
    
    def find_nearest(self, tag: str) -> Optional[dict]:
        """Find the nearest room with a specific tag (shop, inn, bank, etc.)."""
        if not self.map_agent:
            return None
        
        result = self.map_agent._tool_find_nearest_tagged(tag)
        if result.success:
            return result.data
        return None
    
    def add_room_tag(self, room_id: str, tag: str) -> bool:
        """Add a tag to a room."""
        if not self.map_agent:
            return False
        result = self.map_agent._tool_add_room_tag(room_id, tag)
        return result.success
    
    def add_room_note(self, room_id: str, note: str) -> bool:
        """Add a note to a room."""
        if not self.map_agent:
            return False
        result = self.map_agent._tool_add_room_note(room_id, note)
        return result.success
    
    def set_room_image(self, room_id: str, image_path: str, prompt: str = "") -> bool:
        """Set the image path for a room."""
        if not self.map_agent:
            return False
        result = self.map_agent._tool_set_room_image(room_id, image_path, prompt)
        return result.success
    
    def export_map_graphviz(self) -> Optional[str]:
        """Export the map as Graphviz DOT format."""
        if not self.map_agent:
            return None
        return self.map_agent.export_graphviz()
