# LLMUD - AI-Powered MUD Client

A Python package for connecting to MUDs (Multi-User Dungeons) with LLM-driven gameplay.

## Features

- **Telnet Connection**: Full telnet protocol support with GMCP (Generic MUD Communication Protocol)
- **LLM Integration**: Support for OpenAI and Anthropic APIs for AI-driven decision making
- **Context Management**: Smart context window management to keep strategy in focus while rotating game data
- **Game State Tracking**: Automatic parsing of game output and GMCP data
- **Session Management**: High-level orchestration of gameplay

## Installation

```bash
pip install llmud
```

Or install from source:

```bash
cd mud_client
pip install -e .
```

## Quick Start

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

## License

MIT
