"""
Agentic MUD Session - Orchestrator for AI-driven MUD gameplay.

Key design principles:
1. Mapper and GMCP tracking run continuously regardless of who is typing
2. AI agent interacts via tool calls
3. Clean separation between infrastructure (telnet, GMCP, mapping) and AI control
"""

import asyncio
import logging
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .telnet_client import TelnetClient
from .gmcp_handler import GMCPHandler
from .game_state import GameState, GamePhase
from .context_manager import ContextManager
from .map_agent import MapAgent
from .agentic_agent import AgenticAgent

logger = logging.getLogger(__name__)


@dataclass
class AgenticSessionConfig:
    """Configuration for an agentic MUD session."""
    host: str = "dunemud.net"
    port: int = 6789
    username: str = ""
    password: str = ""
    
    # AI Configuration
    openai_api_key: str = ""
    model: str = "gpt-4o"  # Use gpt-4o for good balance of capability and speed
    knowledge_path: str = "./knowledge_base.json"
    
    # Mapping Configuration
    map_enabled: bool = True
    map_path: str = "./world_map.json"
    map_auto_save: bool = True
    
    # Session Configuration
    auto_play: bool = False
    command_delay: float = 1.5  # Seconds between AI actions


@dataclass
class SessionEvent:
    """Event from the session."""
    type: str  # "text", "gmcp", "command", "ai_action", "state_change"
    data: Any
    timestamp: datetime = field(default_factory=datetime.now)


class AgenticSession:
    """
    Agentic MUD Session orchestrator.
    
    This session:
    1. Maintains telnet connection and handles GMCP
    2. Runs the mapper continuously
    3. Tracks game state from text output
    4. Provides an AI agent that can take control via tool calls
    """
    
    def __init__(self, config: AgenticSessionConfig):
        self.config = config
        
        # Core infrastructure (always running)
        self.telnet = TelnetClient(config.host, config.port)
        self.gmcp = GMCPHandler()
        self.game_state = GameState()
        
        # Map agent (runs independently of AI)
        self.map_agent: Optional[MapAgent] = None
        if config.map_enabled:
            self.map_agent = MapAgent(
                provider="openai",
                api_key=config.openai_api_key,
                map_path=config.map_path,
                auto_save=config.map_auto_save,
            )
        
        # AI Agent (optional, can be enabled/disabled)
        self.agent: Optional[AgenticAgent] = None
        if config.openai_api_key:
            self.agent = AgenticAgent(
                api_key=config.openai_api_key,
                model=config.model,
                knowledge_path=config.knowledge_path,
            )
            # Set up callbacks
            self.agent.set_callbacks(
                send_command=self.send_command,
                get_state=self.get_game_state,
                get_output=self._get_recent_output,
                map_agent=self.map_agent,
            )
        
        # Session state
        self._running = False
        self._ai_active = config.auto_play
        self._paused = False
        
        # Event callbacks
        self._event_callbacks: list[Callable[[SessionEvent], Any]] = []
        
        # Command queue for manual input
        self._command_queue: asyncio.Queue[str] = asyncio.Queue()
        
        # Output buffer for AI
        self._output_buffer: list[str] = []
        self._max_output_buffer = 100
        
        # Track movement for mapping
        self._last_movement_direction: Optional[str] = None
        
        # Set up internal callbacks
        self._setup_callbacks()
    
    def _setup_callbacks(self) -> None:
        """Set up internal callbacks for telnet and GMCP."""
        self.telnet.on_text(self._on_text)
        self.telnet.on_gmcp(self._on_gmcp)
        
        self.gmcp.on_vitals_change(self._on_vitals_change)
        self.gmcp.on_room_change(self._on_room_change)
        self.gmcp.on_channel_message(self._on_channel_message)
    
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
    
    # ==================== Telnet Callbacks ====================
    
    async def _on_text(self, text: str) -> None:
        """Handle received text from MUD."""
        # Update game state
        self.game_state.process_text(text)
        
        # Add to output buffer for AI
        self._output_buffer.append(text)
        if len(self._output_buffer) > self._max_output_buffer:
            self._output_buffer.pop(0)
        
        # Also pass to agent if active
        if self.agent:
            self.agent.add_mud_output(text)
        
        # Emit event
        self._emit_event("text", {
            "text": text,
            "phase": self.game_state.phase.name,
        })
    
    async def _on_gmcp(self, module: str, data: Any) -> None:
        """Handle GMCP message."""
        # Process through GMCP handler
        self.gmcp.process(module, data)
        
        # Emit event
        self._emit_event("gmcp", {
            "module": module,
            "data": data,
        })
    
    def _on_vitals_change(self, vitals) -> None:
        """Handle vitals change from GMCP."""
        self._emit_event("state_change", {
            "type": "vitals",
            "data": self.gmcp.get_state_summary(),
        })
    
    def _on_room_change(self, room) -> None:
        """Handle room change from GMCP."""
        # Update game state
        self.game_state.update_from_gmcp(
            room_id=room.num,
            room_name=room.name,
            area=room.area,
            exits=room.get_exit_directions(),
        )
        
        # Update mapper (runs regardless of AI)
        if self.map_agent:
            if self._last_movement_direction:
                self.map_agent.record_movement(
                    self._last_movement_direction,
                    room.num
                )
                self._last_movement_direction = None
            
            self.map_agent.update_from_gmcp(
                room_id=room.num,
                room_name=room.name,
                area=room.area,
                environment=room.environment,
                exits=room.exits,
            )
        
        # Emit event
        self._emit_event("room_change", {
            "room_id": room.num,
            "room_name": room.name,
            "area": room.area,
            "exits": room.get_exit_directions(),
        })
    
    def _on_channel_message(self, message) -> None:
        """Handle channel message."""
        self._emit_event("chat", {
            "channel": message.channel,
            "talker": message.talker,
            "text": message.text,
        })
    
    # ==================== Connection Management ====================
    
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
    
    async def login(self, username: str = "", password: str = "") -> None:
        """Login to the MUD."""
        username = username or self.config.username
        password = password or self.config.password
        
        if username:
            await asyncio.sleep(1)
            await self.send_command(username)
        
        if password:
            await asyncio.sleep(0.5)
            await self.send_command(password)
    
    # ==================== Command Handling ====================
    
    async def send_command(self, command: str) -> None:
        """Send a command to the MUD."""
        if not command:
            return
        
        # Track movement for mapper
        movement_commands = {
            "n", "s", "e", "w", "ne", "nw", "se", "sw", "u", "d",
            "north", "south", "east", "west", "up", "down",
            "northeast", "northwest", "southeast", "southwest",
            "enter", "out",
        }
        cmd_lower = command.lower().strip()
        if cmd_lower in movement_commands:
            direction_map = {
                "north": "n", "south": "s", "east": "e", "west": "w",
                "up": "u", "down": "d",
                "northeast": "ne", "northwest": "nw",
                "southeast": "se", "southwest": "sw",
            }
            self._last_movement_direction = direction_map.get(cmd_lower, cmd_lower)
        
        # Record command
        self.game_state.record_command(command)
        
        # Send via telnet
        await self.telnet.send(command)
        
        # Emit event
        self._emit_event("command", {
            "command": command,
            "source": "manual" if not self._ai_active else "ai",
        })
    
    async def queue_command(self, command: str) -> None:
        """Queue a command for sending (for external input)."""
        await self._command_queue.put(command)
    
    # ==================== AI Control ====================
    
    def set_ai_active(self, active: bool) -> None:
        """Enable or disable AI control."""
        self._ai_active = active
        self._emit_event("ai_mode", {"active": active})
    
    def is_ai_active(self) -> bool:
        """Check if AI is active."""
        return self._ai_active
    
    def pause_ai(self) -> None:
        """Pause AI without disabling it."""
        self._paused = True
        self._emit_event("ai_paused", {})
    
    def resume_ai(self) -> None:
        """Resume AI."""
        self._paused = False
        self._emit_event("ai_resumed", {})
    
    async def set_agent_goal(self, goal: str, priority: str = "medium") -> None:
        """Set a goal for the AI agent."""
        if self.agent:
            self.agent._tool_set_goal(goal, priority)
            self._emit_event("goal_set", {"goal": goal, "priority": priority})
    
    def get_agent_state(self) -> Optional[dict]:
        """Get the AI agent's current state."""
        if self.agent:
            return self.agent.get_state_summary()
        return None
    
    # ==================== State Access ====================
    
    def get_game_state(self) -> dict:
        """Get current game state for the AI."""
        return self.gmcp.get_state_summary()
    
    def _get_recent_output(self) -> str:
        """Get recent output for the AI."""
        return "\n".join(self._output_buffer[-30:])
    
    def get_full_state(self) -> dict:
        """Get complete session state."""
        state = {
            "connected": self.telnet.connected,
            "phase": self.game_state.phase.name,
            "ai_active": self._ai_active,
            "paused": self._paused,
            "character": self.gmcp.get_state_summary(),
            "room": self.game_state.get_room_context(),
        }
        
        if self.map_agent:
            state["map_stats"] = self.map_agent.get_map_stats()
        
        if self.agent:
            state["agent"] = self.agent.get_state_summary()
        
        return state
    
    def get_map_data(self) -> Optional[dict]:
        """Get map data for visualization."""
        if self.map_agent:
            return self.map_agent.get_map_data_for_visualization()
        return None
    
    # ==================== Main Loop ====================
    
    async def run(self) -> None:
        """Main session loop."""
        self._running = True
        logger.info("Starting agentic session loop")
        
        ai_cooldown = 0
        last_ai_time = 0
        
        while self._running:
            try:
                # Check connection
                if not self.telnet.connected:
                    logger.warning("Connection lost")
                    self._running = False
                    self._emit_event("disconnected", {"error": "Connection lost"})
                    break
                
                # Receive data from MUD
                await self.telnet.receive()
                
                # Process manual command queue
                try:
                    command = self._command_queue.get_nowait()
                    await self.send_command(command)
                except asyncio.QueueEmpty:
                    pass
                
                # AI action (if active and not paused)
                import time
                current_time = time.time()
                if (self._ai_active and not self._paused and self.agent and 
                    current_time - last_ai_time >= self.config.command_delay):
                    # Let the AI think and act
                    try:
                        await self._ai_think_cycle()
                        last_ai_time = current_time
                    except Exception as ae:
                        logger.error(f"AI think cycle error: {ae}")
                
                # Small delay to prevent tight loop
                await asyncio.sleep(0.05)
                
            except asyncio.CancelledError:
                logger.info("Session loop cancelled")
                break
            except Exception as e:
                logger.error(f"Session loop error: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(0.5)  # Prevent tight error loop
    
    async def _ai_think_cycle(self) -> None:
        """Run one AI thinking cycle."""
        if not self.agent:
            return
        
        try:
            # Get current state
            game_state = self.get_game_state()
            recent_output = self._get_recent_output()
            
            # Let agent think and act
            results = await self.agent.think_and_act(
                game_state=game_state,
                recent_output=recent_output,
                max_tool_calls=5,  # Limit per cycle
            )
            
            # Emit event for each action
            for result in results:
                self._emit_event("ai_action", {
                    "success": result.success,
                    "result": result.result,
                    "message": result.message,
                })
            
            # Check if goal is complete
            if self.agent.is_goal_complete():
                goal_result = self.agent.get_goal_result()
                self._emit_event("goal_complete", goal_result)
                self.agent.reset_goal()
                self._ai_active = False  # Pause after goal complete
        
        except Exception as e:
            logger.error(f"AI think cycle error: {e}")
            self._emit_event("ai_error", {"error": str(e)})
    
    async def run_goal(self, goal: str, timeout: float = 300) -> dict:
        """
        Run the AI until a goal is achieved or timeout.
        
        Args:
            goal: The goal to achieve
            timeout: Maximum time in seconds
            
        Returns:
            Goal result dict with success status and summary
        """
        if not self.agent:
            return {"success": False, "summary": "No AI agent configured"}
        
        await self.set_agent_goal(goal)
        self.set_ai_active(True)
        
        start_time = asyncio.get_event_loop().time()
        
        while self._running and self._ai_active:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                return {"success": False, "summary": f"Timeout after {elapsed:.0f}s"}
            
            if self.agent.is_goal_complete():
                return self.agent.get_goal_result() or {"success": True, "summary": "Goal complete"}
            
            await asyncio.sleep(0.1)
        
        return {"success": False, "summary": "Session ended before goal completion"}


# ==================== Helper Functions ====================

async def create_session(
    host: str = "dunemud.net",
    port: int = 6789,
    openai_api_key: str = "",
    username: str = "",
    password: str = "",
    **kwargs
) -> AgenticSession:
    """Create and connect an agentic session."""
    config = AgenticSessionConfig(
        host=host,
        port=port,
        openai_api_key=openai_api_key,
        username=username,
        password=password,
        **kwargs
    )
    
    session = AgenticSession(config)
    await session.connect()
    return session


async def quick_test(
    goal: str,
    host: str = "dunemud.net",
    port: int = 6789,
    openai_api_key: str = "",
    username: str = "",
    password: str = "",
    timeout: float = 120,
) -> dict:
    """
    Quick test of a goal against the MUD.
    
    Args:
        goal: The goal to test
        host: MUD host
        port: MUD port
        openai_api_key: OpenAI API key
        username: Character name
        password: Character password
        timeout: Maximum time in seconds
        
    Returns:
        Goal result dict
    """
    session = await create_session(
        host=host,
        port=port,
        openai_api_key=openai_api_key,
        username=username,
        password=password,
    )
    
    try:
        if username and password:
            await session.login()
            await asyncio.sleep(3)  # Wait for login
        
        # Start the session loop in background
        loop_task = asyncio.create_task(session.run())
        
        # Run the goal
        result = await session.run_goal(goal, timeout=timeout)
        
        # Clean up
        session._running = False
        await asyncio.sleep(0.5)
        loop_task.cancel()
        
        return result
    
    finally:
        await session.disconnect()
