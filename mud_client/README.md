# LLMUD - AI-Powered MUD Client

A Python package for connecting to MUDs (Multi-User Dungeons) with LLM-driven gameplay.

## Features

- **Terminal App**: Claude Code-style terminal client with local commands
- **Telnet Connection**: Full telnet protocol support with GMCP (Generic MUD Communication Protocol)
- **LLM Integration**: Support for OpenAI and Anthropic APIs for AI-driven decision making
- **Context Management**: Smart context window management to keep strategy in focus while rotating game data
- **Game State Tracking**: Automatic parsing of game output and GMCP data
- **Session Management**: High-level orchestration of gameplay
- **Mapping Agent**: LLM-powered automatic world mapping with pathfinding

## Installation

```bash
pip install llmud
```

Or install from source:

```bash
cd mud_client
pip install -e .
```

## Terminal App (Recommended)

The easiest way to use LLMUD is via the terminal app:

```bash
# Start the terminal app
llmud

# Or with auto-connect
llmud --auto-connect

# Or with auto-login
llmud -u YourUsername -p YourPassword --auto-connect --auto-login
```

### Local Commands

All local commands start with `/` and are NOT sent to the MUD server:

| Command | Description |
|---------|-------------|
| `/help` | Show help message |
| `/ai` | Get AI command suggestion |
| `/y`, `/yes` | Confirm and send pending AI suggestion |
| `/n`, `/no` | Reject pending AI suggestion |
| `/status` | Show current game status |
| `/config` | Show current configuration |
| `/set <key> <value>` | Change a setting |
| `/connect [host] [port]` | Connect to MUD server |
| `/disconnect` | Disconnect from server |
| `/login [user] [pass]` | Login with credentials |
| `/provider <openai\|anthropic>` | Set AI provider |
| `/model <name>` | Set AI model |
| `/gmcp` | Toggle GMCP message display |
| `/map` | Show explored rooms |
| `/context` | Show AI context token usage |
| `/clear` | Clear screen |
| `/quit` | Exit application |

### AI Suggestions

Use `/ai` to get an AI-powered command suggestion:

```
❯ /ai
ℹ Thinking...
┌─ 🤖 AI Suggestion ─────────────────────────────────┐
│ north                                               │
│                                                     │
│ Model: gpt-4o-mini, Tokens: 342                    │
└────────────────────────────────────────────────────┘
Send this command? /y to confirm, /n to reject, or type your own command
```

Then use `/y` to send it or `/n` to reject.

## Quick Start (Programmatic)

```python
import asyncio
from llmud import MUDSession, SessionConfig

async def main():
    config = SessionConfig(
        host="dunemud.net",
        port=6789,
        username="your_username",
        password="your_password",
        llm_provider="anthropic",  # or "openai"
        llm_api_key="your_api_key",
        auto_play=True,
    )
    
    session = MUDSession(config)
    
    # Register event handler
    session.on_event(lambda e: print(f"Event: {e.type}"))
    
    # Connect and run
    if await session.connect():
        await session.login()
        await session.run()

asyncio.run(main())
```

## Components

### TelnetClient

Low-level telnet connection with GMCP support:

```python
from llmud import TelnetClient

client = TelnetClient("dunemud.net", 6789)
client.on_text(lambda text: print(text))
client.on_gmcp(lambda module, data: print(f"GMCP: {module}"))

await client.connect()
await client.send("look")
```

### GMCPHandler

Processes GMCP messages and maintains game state:

```python
from llmud import GMCPHandler

handler = GMCPHandler()
handler.on_vitals_change(lambda v: print(f"HP: {v.hp}/{v.maxhp}"))
handler.on_room_change(lambda r: print(f"Room: {r.name}"))
```

### LLMAgent

Interface to LLM providers for decision making:

```python
from llmud import LLMAgent

agent = LLMAgent(provider="anthropic", api_key="...")
response = await agent.get_command(system_prompt, user_prompt)
print(f"Command: {response.command}")
```

### ContextManager

Manages LLM context with efficient token usage:

```python
from llmud import ContextManager

context = ContextManager(strategy_path="strategy.md")
context.update_game_state({"character": {...}})
context.update_current_room({"name": "...", "exits": [...]})

prompt = context.build_user_prompt("Kill mobs for experience")
```

### MapAgent

LLM-powered mapping agent that builds and maintains a world map:

```python
from llmud import MapAgent

# Create a mapping agent
agent = MapAgent(
    provider="anthropic",
    api_key="your_api_key",
    map_path="world_map.json",  # Auto-saves here
    auto_save=True,
)

# Update from GMCP room data
agent.update_from_gmcp(
    room_id="room123",
    room_name="Town Square",
    area="Arrakeen",
    environment="city",
    exits={"n": "room124", "s": "room125"},
)

# Find routes
route = agent.get_route_to("shop")  # By tag
route = agent.get_route_to("room456")  # By ID

# Use LLM to analyze room descriptions
results = await agent.analyze_room_text(room_description)

# Get map data for visualization
map_data = agent.get_map_data_for_visualization()
```

### MapGraph

Graph data structure for the world map:

```python
from llmud import MapGraph, RoomNode

# Create a map
world_map = MapGraph(name="dune_world")

# Add rooms
room = RoomNode(
    room_id="room1",
    name="Town Square",
    area="Arrakeen",
    description="A bustling town square.",
    tags=["shop", "safe"],
)
world_map.add_room(room)

# Add connections
world_map.add_edge("room1", "room2", direction="n")

# Pathfinding
path = world_map.find_path("room1", "room5")  # Returns ["n", "e", "e"]
route = world_map.get_route_commands("room1", "room5")  # Returns "n;2e"

# Find rooms by tag
shops = world_map.find_rooms_by_tag("shop")
nearest = world_map.find_nearest_by_tag("room1", "inn")

# Persistence
world_map.save_json("map.json")
loaded = MapGraph.load_json("map.json")

# Export for visualization
world_map.auto_layout()  # Calculate positions
dot_format = agent.export_graphviz()  # Export as DOT
```

## Configuration

### Environment Variables

- `ANTHROPIC_API_KEY`: Anthropic Claude API key
- `OPENAI_API_KEY`: OpenAI API key

### SessionConfig Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| host | str | "dunemud.net" | MUD server hostname |
| port | int | 6789 | MUD server port |
| username | str | "" | Login username |
| password | str | "" | Login password |
| strategy_path | str | "" | Path to strategy.md file |
| llm_provider | str | "anthropic" | LLM provider ("anthropic" or "openai") |
| llm_api_key | str | "" | API key (or use env var) |
| llm_model | str | "" | Model name (uses defaults if empty) |
| auto_play | bool | False | Enable AI auto-play |
| command_delay | float | 2.0 | Seconds between AI commands |
| map_enabled | bool | True | Enable automatic mapping |
| map_path | str | "" | Path to save/load map JSON file |
| map_auto_save | bool | True | Auto-save map on changes |
| map_images_dir | str | "" | Directory to store room images |
| map_llm_analysis | bool | False | Use LLM to analyze room descriptions |

## License

MIT
