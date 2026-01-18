"""
Terminal MUD Client - Claude Code style terminal application.

A standalone terminal app for playing MUDs with AI assistance.
Supports local commands (prefixed with /) that aren't sent to the server.
"""

import asyncio
import os
import sys
import re
import logging
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum, auto

from dotenv import load_dotenv

# Rich for beautiful terminal output
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.layout import Layout
from rich.style import Style
from rich.markup import escape
from rich import box

from .telnet_client import TelnetClient
from .gmcp_handler import GMCPHandler
from .game_state import GameState, GamePhase
from .context_manager import ContextManager
from .llm_agent import LLMAgent, LLMResponse

# Load environment
load_dotenv()

# Configure logging to file only (keep terminal clean)
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('llmud.log', mode='a')]
)
logger = logging.getLogger(__name__)


class AIProvider(Enum):
    """Available AI providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class AppConfig:
    """Terminal app configuration."""
    host: str = "dunemud.net"
    port: int = 6789
    username: str = ""
    password: str = ""
    ai_provider: AIProvider = AIProvider.OPENAI
    ai_model: str = ""
    strategy_path: str = ""
    auto_login: bool = False
    show_gmcp: bool = False
    ansi_colors: bool = True


@dataclass
class AIThought:
    """Represents AI's reasoning about a decision."""
    observation: str  # What the AI sees
    thinking: str     # Why it chose this action
    goal: str         # Current goal
    command: str      # The suggested command
    confidence: str   # How confident (low/medium/high)


class TerminalApp:
    """
    Claude Code-style terminal MUD client.
    
    Features:
    - Direct telnet connection to MUD
    - Local commands with / prefix
    - AI command suggestions with /ai
    - Auto-AI mode with /auto
    - AI diary/reasoning display
    - Rich terminal formatting
    - GMCP support for game state
    """

    # Color scheme (Dune-inspired desert tones)
    COLORS = {
        "primary": "#D4A574",      # Sand
        "secondary": "#8B7355",    # Brown
        "accent": "#C19A6B",       # Camel
        "success": "#9CAF88",      # Sage green
        "warning": "#DAA520",      # Goldenrod
        "error": "#CD5C5C",        # Indian red
        "info": "#87CEEB",         # Sky blue
        "muted": "#696969",        # Dim gray
        "ai": "#B19CD9",           # Light purple (AI suggestions)
        "command": "#98D8C8",      # Mint (commands)
        "thinking": "#FFB347",     # Orange (AI thinking)
    }

    BANNER = r"""
[#D4A574]
  ██╗     ██╗     ███╗   ███╗██╗   ██╗██████╗ 
  ██║     ██║     ████╗ ████║██║   ██║██╔══██╗
  ██║     ██║     ██╔████╔██║██║   ██║██║  ██║
  ██║     ██║     ██║╚██╔╝██║██║   ██║██║  ██║
  ███████╗███████╗██║ ╚═╝ ██║╚██████╔╝██████╔╝
  ╚══════╝╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═════╝ 
[/]
[#8B7355]  AI-Powered MUD Client • DuneMUD Edition[/]
"""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.console = Console(highlight=False)
        
        # Connection components
        self.telnet: Optional[TelnetClient] = None
        self.gmcp = GMCPHandler()
        self.state = GameState()
        self.context: Optional[ContextManager] = None
        self.agent: Optional[LLMAgent] = None
        
        # App state
        self._running = False
        self._connected = False
        self._auto_mode = False  # Auto-AI mode
        self._input_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        
        # Command history
        self._history: list[str] = []
        self._history_index = 0
        
        # Pending AI suggestion
        self._pending_ai_command: Optional[str] = None
        self._pending_ai_thought: Optional[AIThought] = None
        
        # Current goal
        self._current_goal: str = "Explore the world and learn about my surroundings"
        
        # AI diary (recent thoughts)
        self._ai_diary: list[AIThought] = []
        
        # Partial line buffer for prompts without newlines
        self._partial_line: str = ""
        
        # Register local commands
        self._local_commands = self._register_commands()

    def _register_commands(self) -> dict[str, Callable]:
        """Register local / commands."""
        return {
            "help": self._cmd_help,
            "h": self._cmd_help,
            "?": self._cmd_help,
            "ai": self._cmd_ai,
            "suggest": self._cmd_ai,
            "auto": self._cmd_auto,
            "stop": self._cmd_stop,
            "goal": self._cmd_goal,
            "diary": self._cmd_diary,
            "think": self._cmd_think,
            "status": self._cmd_status,
            "stat": self._cmd_status,
            "config": self._cmd_config,
            "set": self._cmd_set,
            "connect": self._cmd_connect,
            "disconnect": self._cmd_disconnect,
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
            "q": self._cmd_quit,
            "clear": self._cmd_clear,
            "cls": self._cmd_clear,
            "gmcp": self._cmd_gmcp,
            "map": self._cmd_map,
            "history": self._cmd_history,
            "login": self._cmd_login,
            "provider": self._cmd_provider,
            "model": self._cmd_model,
            "context": self._cmd_context,
            "y": self._cmd_confirm_yes,
            "yes": self._cmd_confirm_yes,
            "n": self._cmd_confirm_no,
            "no": self._cmd_confirm_no,
            "": self._cmd_confirm_yes,  # Enter = yes in auto mode
        }

    def _print_banner(self) -> None:
        """Print the app banner."""
        self.console.print(self.BANNER)
        self.console.print()

    def _print_help(self) -> None:
        """Print help for local commands."""
        table = Table(
            title="[bold]Local Commands[/bold]",
            box=box.ROUNDED,
            border_style=self.COLORS["secondary"],
            title_style=self.COLORS["primary"],
        )
        
        table.add_column("Command", style=self.COLORS["command"])
        table.add_column("Description", style="white")
        
        commands = [
            ("/help, /h, /?", "Show this help message"),
            ("/ai, /suggest", "Get one AI command suggestion"),
            ("/auto", "Start auto-AI mode (continuous suggestions)"),
            ("/stop", "Stop auto-AI mode"),
            ("/y, /yes, Enter", "Confirm and send pending AI command"),
            ("/n, /no", "Reject pending AI command"),
            ("/goal <text>", "Set current goal for AI"),
            ("/diary", "Show AI's recent thinking diary"),
            ("/think", "Show AI's last reasoning"),
            ("/status, /stat", "Show current game status"),
            ("/config", "Show current configuration"),
            ("/set <key> <value>", "Set configuration value"),
            ("/connect [host] [port]", "Connect to MUD server"),
            ("/disconnect", "Disconnect from server"),
            ("/login [user] [pass]", "Login with credentials"),
            ("/provider <openai|anthropic>", "Set AI provider"),
            ("/model <model_name>", "Set AI model"),
            ("/gmcp", "Toggle GMCP message display"),
            ("/map", "Show explored map"),
            ("/context", "Show current AI context"),
            ("/history", "Show command history"),
            ("/clear, /cls", "Clear the screen"),
            ("/quit, /exit, /q", "Exit the application"),
        ]
        
        for cmd, desc in commands:
            table.add_row(cmd, desc)
        
        self.console.print(table)
        self.console.print()
        self.console.print(
            f"[{self.COLORS['muted']}]Tip: Any input not starting with / is sent directly to the MUD[/]"
        )
        self.console.print(
            f"[{self.COLORS['muted']}]Tip: Use /auto for hands-free AI play, press Enter to approve or /n to reject[/]"
        )

    def _print_status(self) -> None:
        """Print current status."""
        conn_status = "🟢 Connected" if self._connected else "🔴 Disconnected"
        auto_status = "🤖 Auto-AI ON" if self._auto_mode else "⏸️  Manual"
        
        table = Table(
            title="[bold]Status[/bold]",
            box=box.ROUNDED,
            border_style=self.COLORS["secondary"],
        )
        
        table.add_column("Property", style=self.COLORS["accent"])
        table.add_column("Value", style="white")
        
        table.add_row("Connection", conn_status)
        table.add_row("AI Mode", auto_status)
        table.add_row("Server", f"{self.config.host}:{self.config.port}")
        table.add_row("AI Provider", self.config.ai_provider.value)
        table.add_row("AI Model", self.config.ai_model or "default")
        table.add_row("Current Goal", self._current_goal[:50] + "..." if len(self._current_goal) > 50 else self._current_goal)
        
        if self._connected:
            table.add_row("Game Phase", self.state.phase.name)
            
            gmcp_summary = self.gmcp.get_state_summary()
            if gmcp_summary.get("name"):
                table.add_row("Character", gmcp_summary.get("name", "Unknown"))
                table.add_row("Guild", gmcp_summary.get("guild", "None"))
                table.add_row("Level", str(gmcp_summary.get("level", "?")))
                
                hp = gmcp_summary.get("hp", "?")
                hp_pct = gmcp_summary.get("hp_percent", 0)
                hp_style = self.COLORS["success"] if hp_pct > 50 else self.COLORS["warning"] if hp_pct > 25 else self.COLORS["error"]
                table.add_row("HP", f"[{hp_style}]{hp} ({hp_pct}%)[/]")
        
        self.console.print(table)

    def _print_config(self) -> None:
        """Print current configuration."""
        table = Table(
            title="[bold]Configuration[/bold]",
            box=box.ROUNDED,
            border_style=self.COLORS["secondary"],
        )
        
        table.add_column("Setting", style=self.COLORS["accent"])
        table.add_column("Value", style="white")
        
        table.add_row("host", self.config.host)
        table.add_row("port", str(self.config.port))
        table.add_row("username", self.config.username or "[dim]not set[/]")
        table.add_row("password", "****" if self.config.password else "[dim]not set[/]")
        table.add_row("ai_provider", self.config.ai_provider.value)
        table.add_row("ai_model", self.config.ai_model or "[dim]default[/]")
        table.add_row("strategy_path", self.config.strategy_path or "[dim]default[/]")
        table.add_row("show_gmcp", str(self.config.show_gmcp))
        
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
        
        table.add_row("OPENAI_API_KEY", "✓ set" if has_openai else "[dim]not set[/]")
        table.add_row("ANTHROPIC_API_KEY", "✓ set" if has_anthropic else "[dim]not set[/]")
        
        self.console.print(table)

    def _print_mud_output(self, text: str, is_partial: bool = False) -> None:
        """Print MUD output with optional ANSI handling."""
        if not text:
            return
        
        lines = text.split('\n')
        for i, line in enumerate(lines):
            # For the last line without newline, it might be a prompt
            is_last = (i == len(lines) - 1)
            
            if line or not is_last:  # Print non-empty lines or intermediate empty lines
                if self.config.ansi_colors:
                    self.console.print(line, end='\n' if not (is_last and is_partial) else '')
                else:
                    clean = re.sub(r'\x1b\[[0-9;]*m', '', line)
                    self.console.print(clean, end='\n' if not (is_last and is_partial) else '')

    def _print_ai_thought(self, thought: AIThought) -> None:
        """Print AI's reasoning in a nice format."""
        # Build the thought panel content
        content = Text()
        
        # Observation
        content.append("📍 Observation: ", style=f"bold {self.COLORS['info']}")
        content.append(thought.observation[:200] + ("..." if len(thought.observation) > 200 else ""))
        content.append("\n\n")
        
        # Goal
        content.append("🎯 Goal: ", style=f"bold {self.COLORS['warning']}")
        content.append(thought.goal)
        content.append("\n\n")
        
        # Thinking
        content.append("💭 Thinking: ", style=f"bold {self.COLORS['thinking']}")
        content.append(thought.thinking)
        content.append("\n\n")
        
        # Command
        content.append("⚡ Command: ", style=f"bold {self.COLORS['command']}")
        content.append(thought.command, style=f"bold {self.COLORS['ai']}")
        content.append(f"  [{thought.confidence} confidence]", style=self.COLORS['muted'])
        
        panel = Panel(
            content,
            title="[bold]🤖 AI Reasoning[/bold]",
            border_style=self.COLORS["ai"],
            box=box.ROUNDED,
        )
        self.console.print(panel)

    def _print_ai_suggestion(self, thought: AIThought) -> None:
        """Print AI command suggestion with reasoning and confirmation prompt."""
        self._pending_ai_command = thought.command
        self._pending_ai_thought = thought
        
        # Store in diary
        self._ai_diary.append(thought)
        if len(self._ai_diary) > 20:
            self._ai_diary.pop(0)
        
        # Print full reasoning
        self._print_ai_thought(thought)
        
        # Confirmation prompt
        if self._auto_mode:
            self.console.print(
                f"[{self.COLORS['info']}]Press [bold]Enter[/bold] to send, "
                f"[{self.COLORS['command']}]/n[/] to reject, "
                f"or type a different command[/]"
            )
        else:
            self.console.print(
                f"[{self.COLORS['info']}]Send this command? "
                f"[{self.COLORS['command']}]/y[/] to confirm, "
                f"[{self.COLORS['command']}]/n[/] to reject, "
                f"or type your own command[/]"
            )

    def _print_error(self, message: str) -> None:
        """Print an error message."""
        self.console.print(f"[{self.COLORS['error']}]✗ {message}[/]")

    def _print_success(self, message: str) -> None:
        """Print a success message."""
        self.console.print(f"[{self.COLORS['success']}]✓ {message}[/]")

    def _print_info(self, message: str) -> None:
        """Print an info message."""
        self.console.print(f"[{self.COLORS['info']}]ℹ {message}[/]")

    # ==================== AI Methods ====================

    def _get_ai_system_prompt(self) -> str:
        """Get enhanced system prompt for AI with reasoning."""
        base_prompt = self.context.get_system_prompt() if self.context else ""
        
        return f"""{base_prompt}

IMPORTANT: You must respond in a specific JSON format with your reasoning:
{{
    "observation": "Brief description of current situation (room, NPCs, items, HP status)",
    "goal": "Your current objective",
    "thinking": "Your reasoning for the next action - explain WHY you chose this",
    "command": "The MUD command to execute",
    "confidence": "low/medium/high"
}}

RULES FOR GOOD GAMEPLAY:
1. Don't repeat the same command twice in a row unless you have a reason
2. If you just did 'look', don't do 'look' again immediately
3. Explore systematically - try different exits
4. Interact with the environment - read signs, examine items, talk to NPCs
5. Have a clear purpose for each action
6. If at an Astroport, consider traveling to new places
7. Set mini-goals: explore north, find the academy, talk to someone, etc.

Your current goal is: {self._current_goal}
"""

    async def _get_ai_suggestion(self, task: str = "") -> Optional[AIThought]:
        """Get AI suggestion with full reasoning."""
        if not self._connected:
            self._print_error("Not connected to MUD.")
            return None
        
        # Initialize agent if needed
        if not self.agent:
            try:
                api_key = None
                if self.config.ai_provider == AIProvider.OPENAI:
                    api_key = os.getenv("OPENAI_API_KEY")
                else:
                    api_key = os.getenv("ANTHROPIC_API_KEY")
                
                if not api_key:
                    self._print_error(f"No API key for {self.config.ai_provider.value}")
                    return None
                
                self.agent = LLMAgent(
                    provider=self.config.ai_provider.value,
                    api_key=api_key,
                    model=self.config.ai_model or None,
                )
            except Exception as e:
                self._print_error(f"Failed to initialize AI: {e}")
                return None
        
        # Initialize context if needed
        if not self.context:
            self.context = ContextManager(strategy_path=self.config.strategy_path or None)
        
        try:
            system_prompt = self._get_ai_system_prompt()
            user_prompt = self.context.build_user_prompt(task=task or self._current_goal)
            
            # Add recent commands to avoid repetition
            recent_cmds = list(self._history[-5:]) if self._history else []
            if recent_cmds:
                user_prompt += f"\n\nRecent commands sent (avoid repeating): {', '.join(recent_cmds)}"
            
            response = await self.agent.get_command(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.4,  # Slightly higher for variety
            )
            
            # Try to parse JSON response
            import json
            try:
                # Extract JSON from response
                raw = response.raw_response.strip()
                # Handle markdown code blocks
                if "```" in raw:
                    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
                    if match:
                        raw = match.group(1)
                
                data = json.loads(raw)
                thought = AIThought(
                    observation=data.get("observation", "Current game state"),
                    thinking=data.get("thinking", "Analyzing situation..."),
                    goal=data.get("goal", self._current_goal),
                    command=data.get("command", response.command),
                    confidence=data.get("confidence", "medium"),
                )
            except (json.JSONDecodeError, KeyError):
                # Fallback if JSON parsing fails
                thought = AIThought(
                    observation="Analyzing current room and state",
                    thinking=response.raw_response[:200] if response.raw_response else "Deciding next action...",
                    goal=self._current_goal,
                    command=response.command,
                    confidence="medium",
                )
            
            return thought
            
        except Exception as e:
            self._print_error(f"AI error: {e}")
            logger.exception("AI suggestion error")
            return None

    # ==================== Local Command Handlers ====================

    async def _cmd_help(self, args: list[str]) -> None:
        """Show help."""
        self._print_help()

    async def _cmd_ai(self, args: list[str]) -> None:
        """Get one AI command suggestion."""
        self._print_info("Thinking...")
        
        task = " ".join(args) if args else ""
        thought = await self._get_ai_suggestion(task)
        
        if thought:
            self._print_ai_suggestion(thought)

    async def _cmd_auto(self, args: list[str]) -> None:
        """Start auto-AI mode."""
        if not self._connected:
            self._print_error("Not connected. Use /connect first.")
            return
        
        self._auto_mode = True
        self._print_success("Auto-AI mode started! Press Enter to approve suggestions, /n to reject, /stop to exit.")
        
        # Get first suggestion
        self._print_info("Thinking...")
        thought = await self._get_ai_suggestion()
        if thought:
            self._print_ai_suggestion(thought)

    async def _cmd_stop(self, args: list[str]) -> None:
        """Stop auto-AI mode."""
        self._auto_mode = False
        self._pending_ai_command = None
        self._pending_ai_thought = None
        self._print_success("Auto-AI mode stopped.")

    async def _cmd_goal(self, args: list[str]) -> None:
        """Set or show current goal."""
        if not args:
            self.console.print(f"[{self.COLORS['warning']}]🎯 Current goal: {self._current_goal}[/]")
            return
        
        self._current_goal = " ".join(args)
        self._print_success(f"Goal set: {self._current_goal}")

    async def _cmd_diary(self, args: list[str]) -> None:
        """Show AI's recent thinking diary."""
        if not self._ai_diary:
            self._print_info("AI diary is empty. Use /ai to get suggestions.")
            return
        
        self.console.print("[bold]📔 AI Diary - Recent Thoughts[/bold]\n")
        
        for i, thought in enumerate(self._ai_diary[-10:], 1):
            self.console.print(f"[{self.COLORS['muted']}]--- Entry {i} ---[/]")
            self.console.print(f"[{self.COLORS['thinking']}]Goal:[/] {thought.goal}")
            self.console.print(f"[{self.COLORS['info']}]Thinking:[/] {thought.thinking[:100]}...")
            self.console.print(f"[{self.COLORS['command']}]Command:[/] {thought.command}")
            self.console.print()

    async def _cmd_think(self, args: list[str]) -> None:
        """Show last AI reasoning."""
        if self._pending_ai_thought:
            self._print_ai_thought(self._pending_ai_thought)
        elif self._ai_diary:
            self._print_ai_thought(self._ai_diary[-1])
        else:
            self._print_info("No AI thoughts recorded yet. Use /ai first.")

    async def _cmd_confirm_yes(self, args: list[str]) -> None:
        """Confirm and send pending AI command."""
        if self._pending_ai_command:
            cmd = self._pending_ai_command
            self._pending_ai_command = None
            self._pending_ai_thought = None
            await self._send_to_mud(cmd)
            
            # In auto mode, get next suggestion after a delay
            if self._auto_mode:
                await asyncio.sleep(1.5)  # Wait for MUD response
                self._print_info("Thinking...")
                thought = await self._get_ai_suggestion()
                if thought:
                    self._print_ai_suggestion(thought)
        else:
            if not self._auto_mode:
                self._print_info("No pending AI suggestion.")

    async def _cmd_confirm_no(self, args: list[str]) -> None:
        """Reject pending AI command."""
        if self._pending_ai_command:
            self._pending_ai_command = None
            self._pending_ai_thought = None
            self._print_info("Suggestion rejected.")
            
            # In auto mode, get another suggestion
            if self._auto_mode:
                self._print_info("Getting alternative suggestion...")
                thought = await self._get_ai_suggestion()
                if thought:
                    self._print_ai_suggestion(thought)
        else:
            self._print_info("No pending AI suggestion.")

    async def _cmd_status(self, args: list[str]) -> None:
        """Show status."""
        self._print_status()

    async def _cmd_config(self, args: list[str]) -> None:
        """Show configuration."""
        self._print_config()

    async def _cmd_set(self, args: list[str]) -> None:
        """Set configuration value."""
        if len(args) < 2:
            self._print_error("Usage: /set <key> <value>")
            return
        
        key, value = args[0].lower(), " ".join(args[1:])
        
        if key == "host":
            self.config.host = value
        elif key == "port":
            self.config.port = int(value)
        elif key == "username":
            self.config.username = value
        elif key == "password":
            self.config.password = value
        elif key == "ai_provider":
            try:
                self.config.ai_provider = AIProvider(value.lower())
                self.agent = None
            except ValueError:
                self._print_error(f"Invalid provider. Use: openai, anthropic")
                return
        elif key == "ai_model":
            self.config.ai_model = value
            self.agent = None
        elif key == "show_gmcp":
            self.config.show_gmcp = value.lower() in ("true", "1", "yes", "on")
        else:
            self._print_error(f"Unknown setting: {key}")
            return
        
        self._print_success(f"Set {key} = {value}")

    async def _cmd_connect(self, args: list[str]) -> None:
        """Connect to MUD."""
        if self._connected:
            self._print_error("Already connected. Use /disconnect first.")
            return
        
        if len(args) >= 1:
            self.config.host = args[0]
        if len(args) >= 2:
            self.config.port = int(args[1])
        
        self._print_info(f"Connecting to {self.config.host}:{self.config.port}...")
        
        try:
            self.telnet = TelnetClient(self.config.host, self.config.port)
            
            # Register callbacks
            self.telnet.on_text(self._on_mud_text)
            self.telnet.on_gmcp(self._on_gmcp)
            
            success = await self.telnet.connect()
            
            if success:
                self._connected = True
                self._print_success(f"Connected to {self.config.host}:{self.config.port}")
                
                # Start receive task
                self._receive_task = asyncio.create_task(self._receive_loop())
                
                # Initialize context
                self.context = ContextManager(strategy_path=self.config.strategy_path or None)
            else:
                self._print_error("Connection failed")
                
        except Exception as e:
            self._print_error(f"Connection error: {e}")

    async def _cmd_disconnect(self, args: list[str]) -> None:
        """Disconnect from MUD."""
        if not self._connected:
            self._print_info("Not connected.")
            return
        
        self._auto_mode = False
        await self._disconnect()
        self._print_success("Disconnected")

    async def _cmd_login(self, args: list[str]) -> None:
        """Login to MUD."""
        if not self._connected:
            self._print_error("Not connected. Use /connect first.")
            return
        
        username = args[0] if len(args) >= 1 else self.config.username
        password = args[1] if len(args) >= 2 else self.config.password
        
        if not username:
            self._print_error("No username. Use /login <user> <pass>")
            return
        
        self._print_info(f"Logging in as {username}...")
        
        await self._send_to_mud(username)
        await asyncio.sleep(1)
        
        if password:
            await self._send_to_mud(password)

    async def _cmd_quit(self, args: list[str]) -> None:
        """Quit application."""
        self._running = False
        self._auto_mode = False
        if self._connected:
            await self._disconnect()
        self._print_info("Goodbye!")

    async def _cmd_clear(self, args: list[str]) -> None:
        """Clear screen."""
        self.console.clear()
        self._print_banner()

    async def _cmd_gmcp(self, args: list[str]) -> None:
        """Toggle GMCP display."""
        self.config.show_gmcp = not self.config.show_gmcp
        state = "enabled" if self.config.show_gmcp else "disabled"
        self._print_success(f"GMCP display {state}")

    async def _cmd_map(self, args: list[str]) -> None:
        """Show explored map."""
        if not self.state.world_map:
            self._print_info("No rooms explored yet.")
            return
        
        table = Table(
            title="[bold]Explored Rooms[/bold]",
            box=box.ROUNDED,
            border_style=self.COLORS["secondary"],
        )
        
        table.add_column("Room", style=self.COLORS["primary"])
        table.add_column("Area", style=self.COLORS["accent"])
        table.add_column("Exits", style=self.COLORS["muted"])
        table.add_column("Visits", style="white")
        
        for room_id, room in list(self.state.world_map.items())[-20:]:
            table.add_row(
                room.name[:30],
                room.area,
                ", ".join(room.exits[:5]),
                str(room.visit_count),
            )
        
        self.console.print(table)
        self._print_info(f"Total rooms explored: {len(self.state.world_map)}")

    async def _cmd_history(self, args: list[str]) -> None:
        """Show command history."""
        if not self._history:
            self._print_info("No command history.")
            return
        
        self.console.print(f"[bold]Command History[/bold] (last 20)")
        for i, cmd in enumerate(self._history[-20:], 1):
            self.console.print(f"  [{self.COLORS['muted']}]{i:3}[/] {cmd}")

    async def _cmd_provider(self, args: list[str]) -> None:
        """Set AI provider."""
        if not args:
            self._print_info(f"Current provider: {self.config.ai_provider.value}")
            return
        
        try:
            self.config.ai_provider = AIProvider(args[0].lower())
            self.agent = None
            self._print_success(f"AI provider set to {self.config.ai_provider.value}")
        except ValueError:
            self._print_error("Invalid provider. Use: openai, anthropic")

    async def _cmd_model(self, args: list[str]) -> None:
        """Set AI model."""
        if not args:
            self._print_info(f"Current model: {self.config.ai_model or 'default'}")
            return
        
        self.config.ai_model = args[0]
        self.agent = None
        self._print_success(f"AI model set to {self.config.ai_model}")

    async def _cmd_context(self, args: list[str]) -> None:
        """Show current AI context."""
        if not self.context:
            self._print_info("No context available.")
            return
        
        usage = self.context.get_token_usage()
        
        table = Table(
            title="[bold]AI Context Usage[/bold]",
            box=box.ROUNDED,
            border_style=self.COLORS["secondary"],
        )
        
        table.add_column("Window", style=self.COLORS["accent"])
        table.add_column("Tokens", style="white")
        
        for name, tokens in usage.items():
            table.add_row(name, str(tokens))
        
        table.add_row("[bold]Total[/bold]", f"[bold]{self.context.get_total_tokens()}[/bold]")
        
        self.console.print(table)

    # ==================== Core Methods ====================

    async def _on_mud_text(self, text: str) -> None:
        """Handle text from MUD."""
        # Combine with any partial line
        if self._partial_line:
            text = self._partial_line + text
            self._partial_line = ""
        
        # Check if text ends with a prompt (no newline)
        # Common prompt patterns: "name:", ">", ">>", etc.
        lines = text.split('\n')
        
        # Print complete lines
        if len(lines) > 1:
            complete_text = '\n'.join(lines[:-1])
            self._print_mud_output(complete_text)
        
        # Handle last line (might be a prompt without newline)
        last_line = lines[-1]
        if last_line:
            # Check if it looks like a prompt (ends with :, >, etc.)
            if re.search(r'[:>]\s*$', last_line) or 'name' in last_line.lower() or 'password' in last_line.lower():
                # Print it immediately as it's likely a prompt
                self._print_mud_output(last_line, is_partial=True)
                self.console.print()  # New line after prompt
            else:
                # Buffer it in case more text is coming
                self._partial_line = last_line
        
        # Update state
        self.state.process_text(text)
        
        # Update context
        if self.context:
            self.context.add_output(text)

    async def _on_gmcp(self, module: str, data: Any) -> None:
        """Handle GMCP message."""
        self.gmcp.process(module, data)
        
        if self.context:
            state_summary = self.gmcp.get_state_summary()
            self.context.update_game_state({"character": state_summary})
            
            if module.startswith("Room"):
                room = self.gmcp.current_room
                if room:
                    self.context.update_current_room({
                        "name": room.name,
                        "area": room.area,
                        "environment": room.environment,
                        "exits": room.get_exit_directions(),
                    })
                    
                    self.state.update_from_gmcp(
                        room_id=room.num,
                        room_name=room.name,
                        area=room.area,
                        exits=room.get_exit_directions(),
                    )
        
        if self.config.show_gmcp:
            self.console.print(f"[{self.COLORS['muted']}]GMCP [{module}]: {data}[/]")

    async def _send_to_mud(self, command: str) -> None:
        """Send command to MUD."""
        if not self._connected or not self.telnet:
            self._print_error("Not connected")
            return
        
        try:
            self._history.append(command)
            await self.telnet.send(command)
            self.console.print(f"[{self.COLORS['command']}]> {command}[/]")
            self.state.record_command(command)
            
        except Exception as e:
            self._print_error(f"Send error: {e}")

    async def _receive_loop(self) -> None:
        """Background task to receive MUD data."""
        while self._connected and self.telnet:
            try:
                await self.telnet.receive()
                
                # Flush partial line if it's been sitting too long
                if self._partial_line:
                    await asyncio.sleep(0.1)
                    if self._partial_line:  # Still there after delay
                        self._print_mud_output(self._partial_line, is_partial=True)
                        self.console.print()
                        self._partial_line = ""
                
                await asyncio.sleep(0.01)
            except Exception as e:
                if self._connected:
                    logger.error(f"Receive error: {e}")
                break

    async def _disconnect(self) -> None:
        """Disconnect from MUD."""
        self._connected = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self.telnet:
            await self.telnet.disconnect()
            self.telnet = None

    async def _handle_input(self, user_input: str) -> None:
        """Handle user input."""
        user_input = user_input.strip()
        
        # In auto mode, empty input = confirm
        if not user_input and self._auto_mode and self._pending_ai_command:
            await self._cmd_confirm_yes([])
            return
        
        if not user_input:
            return
        
        # Check for local command
        if user_input.startswith("/"):
            parts = user_input[1:].split()
            cmd_name = parts[0].lower() if parts else ""
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd_name in self._local_commands:
                await self._local_commands[cmd_name](args)
            else:
                self._print_error(f"Unknown command: /{cmd_name}. Use /help")
        else:
            # Send to MUD
            if self._connected:
                # Clear pending AI command if user types their own
                if self._pending_ai_command:
                    self._pending_ai_command = None
                    self._pending_ai_thought = None
                
                await self._send_to_mud(user_input)
                
                # In auto mode, continue getting suggestions
                if self._auto_mode:
                    await asyncio.sleep(1.5)
                    self._print_info("Thinking...")
                    thought = await self._get_ai_suggestion()
                    if thought:
                        self._print_ai_suggestion(thought)
            else:
                self._print_error("Not connected. Use /connect")

    async def run(self) -> None:
        """Main application loop."""
        self._running = True
        
        self._print_banner()
        self._print_info("Type /help for commands, /auto for AI autopilot mode")
        self.console.print()
        
        while self._running:
            try:
                # Build prompt
                if self._auto_mode:
                    prompt_text = f"[{self.COLORS['ai']}]🤖❯[/] "
                elif self._connected:
                    prompt_text = f"[{self.COLORS['primary']}]❯[/] "
                else:
                    prompt_text = f"[{self.COLORS['muted']}]❯[/] "
                
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.console.input(prompt_text)
                )
                
                await self._handle_input(user_input)
                
            except KeyboardInterrupt:
                self.console.print()
                if self._auto_mode:
                    self._auto_mode = False
                    self._pending_ai_command = None
                    self._print_info("Auto-AI mode stopped. Use /quit to exit.")
                else:
                    self._print_info("Use /quit to exit")
            except EOFError:
                break
            except Exception as e:
                self._print_error(f"Error: {e}")
                logger.exception("Input handling error")
        
        if self._connected:
            await self._disconnect()


def main():
    """Entry point for terminal app."""
    import argparse
    
    parser = argparse.ArgumentParser(description="LLMUD Terminal Client")
    parser.add_argument("--host", default="dunemud.net", help="MUD server host")
    parser.add_argument("--port", type=int, default=6789, help="MUD server port")
    parser.add_argument("--username", "-u", help="Username for auto-login")
    parser.add_argument("--password", "-p", help="Password for auto-login")
    parser.add_argument("--provider", choices=["openai", "anthropic"], default="openai",
                       help="AI provider")
    parser.add_argument("--model", help="AI model name")
    parser.add_argument("--strategy", help="Path to strategy file")
    parser.add_argument("--goal", help="Initial goal for AI")
    parser.add_argument("--auto-connect", "-c", action="store_true",
                       help="Auto-connect on start")
    parser.add_argument("--auto-login", "-l", action="store_true",
                       help="Auto-login after connect")
    parser.add_argument("--auto-ai", "-a", action="store_true",
                       help="Start in auto-AI mode")
    
    args = parser.parse_args()
    
    config = AppConfig(
        host=args.host,
        port=args.port,
        username=args.username or "",
        password=args.password or "",
        ai_provider=AIProvider(args.provider),
        ai_model=args.model or "",
        strategy_path=args.strategy or "",
    )
    
    app = TerminalApp(config)
    
    if args.goal:
        app._current_goal = args.goal
    
    async def run_app():
        if args.auto_connect:
            await app._cmd_connect([])
            
            if args.auto_login and app._connected:
                await asyncio.sleep(1)
                await app._cmd_login([])
                await asyncio.sleep(2)
            
            if args.auto_ai and app._connected:
                await asyncio.sleep(1)
                await app._cmd_auto([])
        
        await app.run()
    
    try:
        asyncio.run(run_app())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
