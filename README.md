# LLMUD - AI-Powered MUD Client

An AI-driven MUD (Multi-User Dungeon) client designed for DuneMUD, featuring LLM-powered gameplay, room visualization, and a modern web interface.

![LLMUD Architecture](https://via.placeholder.com/800x400?text=LLMUD+Architecture)

## Features

### Python MUD Client Package (`mud_client/`)
- **Telnet Connection**: Full telnet protocol support with GMCP (Generic MUD Communication Protocol)
- **LLM Integration**: Support for Anthropic Claude and OpenAI GPT-4 for AI decision making
- **Smart Context Management**: Efficient token usage with strategy always in context
- **Game State Tracking**: Automatic parsing of game output and GMCP data
- **World Mapping**: Track explored rooms and navigation paths

### Web Interface (`frontend/`)
- **Real-time Game Display**: Live MUD text output with ANSI color support
- **Room Visualization**: AI-generated images of game locations using Dune aesthetics
- **Dynamic Action Buttons**: Context-aware navigation and combat controls
- **Player Status Dashboard**: HP, CP, stats, money, and location tracking
- **Interactive Map**: Visual representation of explored areas
- **Auto-Play Mode**: Let the AI play while you watch

### Backend API (`backend/`)
- **FastAPI Server**: RESTful API and WebSocket support
- **Session Management**: Multiple concurrent MUD sessions
- **Image Generation**: Integration with Replicate for room visualization

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      React Frontend                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │MUD Output│ │Room Viz  │ │Action Btns│ │Player Sts│       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────┬───────────────────────────────┘
                              │ WebSocket + REST
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│  │Session   │ │LLM Agent │ │Image Gen │                    │
│  │Manager   │ │Interface │ │Service   │                    │
│  └──────────┘ └──────────┘ └──────────┘                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLMUD Python Package                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │Telnet    │ │GMCP      │ │Game      │ │Context   │       │
│  │Client    │ │Handler   │ │State     │ │Manager   │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────┬───────────────────────────────┘
                              │ Telnet + GMCP
                              ▼
                    ┌─────────────────┐
                    │    DuneMUD      │
                    │  dunemud.net    │
                    └─────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- API key for Anthropic or OpenAI

### Local Development

1. **Clone and setup environment:**
```bash
git clone <repo-url>
cd llmud

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install Python dependencies
pip install -r backend/requirements.txt
cd mud_client && pip install -e . && cd ..
```

2. **Configure environment:**
```bash
# Copy example env files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Edit backend/.env and add your API keys
```

3. **Start the backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

4. **Start the frontend (new terminal):**
```bash
cd frontend
npm install
npm run dev
```

5. **Open http://localhost:5173** in your browser

### Using Docker

```bash
# Build and run with Docker Compose
docker-compose up --build

# Frontend: http://localhost:3000
# Backend: http://localhost:8000
```

## Deployment to Render

1. Fork this repository
2. Create a new Render account at [render.com](https://render.com)
3. Connect your GitHub repository
4. Use the Blueprint feature with `render.yaml`
5. Set environment variables:
   - `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
   - `REPLICATE_API_TOKEN` (optional, for image generation)

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes* | Anthropic Claude API key |
| `OPENAI_API_KEY` | Yes* | OpenAI API key |
| `REPLICATE_API_TOKEN` | No | Replicate API for image generation |
| `PORT` | No | Backend port (default: 8000) |
| `VITE_API_URL` | Yes | Frontend → Backend URL |

*At least one LLM API key is required

### Strategy Configuration

The AI uses `strategy.md` to guide gameplay. You can customize:
- Navigation priorities
- Combat strategies
- Leveling approaches
- Guild-specific tactics

## Project Structure

```
llmud/
├── mud_client/              # Python MUD client package
│   └── llmud/
│       ├── telnet_client.py # Telnet + GMCP connection
│       ├── gmcp_handler.py  # GMCP message processing
│       ├── game_state.py    # Game state tracking
│       ├── context_manager.py # LLM context management
│       ├── llm_agent.py     # LLM integration
│       └── mud_session.py   # Session orchestration
├── backend/                 # FastAPI backend
│   └── main.py             # API server
├── frontend/               # React web app
│   └── src/
│       ├── components/     # React components
│       ├── store/          # Zustand state management
│       └── api/            # API client
├── strategy.md             # AI gameplay strategy
├── render.yaml             # Render deployment config
└── docker-compose.yml      # Docker composition
```

## Game Strategy

The AI follows the strategy defined in `strategy.md`, which includes:

1. **Early Game (Levels 1-30)**: Focus on newbie areas, learning commands
2. **Mid Game (Levels 30-100)**: Expand to mid-level zones, join a guild
3. **Late Game (Levels 100+)**: Tackle challenging areas, optimize builds

See [strategy.md](strategy.md) for the complete strategy guide.

## API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/api/config` | Server configuration |
| POST | `/api/sessions` | Create new session |
| GET | `/api/sessions/{id}` | Get session state |
| POST | `/api/sessions/{id}/command` | Send MUD command |
| POST | `/api/sessions/{id}/ai-action` | Request AI action |
| DELETE | `/api/sessions/{id}` | Disconnect session |
| POST | `/api/generate-image` | Generate room image |

### WebSocket

Connect to `/ws/{session_id}` for real-time updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/session_123');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle: text, state_change, chat, ai_action, error
};

// Send commands
ws.send(JSON.stringify({ type: 'command', command: 'look' }));
ws.send(JSON.stringify({ type: 'auto_play', enabled: true }));
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## License

MIT License - see LICENSE file

## Acknowledgments

- [DuneMUD](https://dunemud.net) - The MUD this client is designed for
- [Frank Herbert's Dune](https://en.wikipedia.org/wiki/Dune_(novel)) - The universe that inspired the game
- Anthropic and OpenAI for LLM APIs

---

*"The mystery of life isn't a problem to solve, but a reality to experience."* - Frank Herbert, Dune
