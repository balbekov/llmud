"""
LLMUD Backend API

FastAPI server providing:
- WebSocket connection to MUD
- REST API for game state and actions
- AI-driven gameplay
- Image generation for room visualization
"""

import os
import sys
import json
import asyncio
import logging
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Add mud_client to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mud_client'))

from llmud import MUDSession, SessionConfig, GamePhase

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global session storage (for simplicity - use Redis in production)
sessions: dict[str, MUDSession] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting LLMUD Backend")
    yield
    # Cleanup sessions on shutdown
    for session_id, session in sessions.items():
        try:
            await session.disconnect()
        except Exception:
            pass
    logger.info("LLMUD Backend shutdown")


app = FastAPI(
    title="LLMUD API",
    description="AI-Powered MUD Client Backend",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class ConnectRequest(BaseModel):
    host: str = "dunemud.net"
    port: int = 6789
    username: str = ""
    password: str = ""
    llm_provider: str = "anthropic"
    auto_play: bool = False


class CommandRequest(BaseModel):
    command: str


class AIActionRequest(BaseModel):
    task: str = ""


class ImageGenerationRequest(BaseModel):
    room_name: str
    description: str
    area: str = ""
    environment: str = ""


# REST API Endpoints
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "LLMUD Backend",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/config")
async def get_config():
    """Get default configuration."""
    return {
        "default_host": "dunemud.net",
        "default_port": 6789,
        "llm_providers": ["anthropic", "openai"],
        "has_anthropic_key": bool(os.getenv("ANTHROPIC_API_KEY")),
        "has_openai_key": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.post("/api/sessions")
async def create_session(request: ConnectRequest):
    """Create a new MUD session."""
    session_id = f"session_{len(sessions)}_{datetime.now().timestamp()}"
    
    config = SessionConfig(
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
        llm_provider=request.llm_provider,
        llm_api_key=os.getenv(f"{request.llm_provider.upper()}_API_KEY", ""),
        auto_play=request.auto_play,
        strategy_path=os.path.join(os.path.dirname(__file__), '..', 'strategy.md'),
    )
    
    session = MUDSession(config)
    sessions[session_id] = session
    
    # Connect
    connected = await session.connect()
    if not connected:
        del sessions[session_id]
        raise HTTPException(status_code=500, detail="Failed to connect to MUD")
    
    return {
        "session_id": session_id,
        "connected": True,
        "host": request.host,
    }


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session state."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    return session.get_state()


@app.post("/api/sessions/{session_id}/command")
async def send_command(session_id: str, request: CommandRequest):
    """Send a command to the MUD."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    await session.send_command(request.command)
    
    return {"status": "sent", "command": request.command}


@app.post("/api/sessions/{session_id}/ai-action")
async def ai_action(session_id: str, request: AIActionRequest):
    """Request AI to take an action."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    # Temporarily enable auto mode for one action
    response = await session._ai_decide_and_act()
    
    if response:
        return {
            "command": response.command,
            "model": response.model,
            "tokens": response.tokens_used,
        }
    
    return {"command": None, "message": "No action taken"}


@app.post("/api/sessions/{session_id}/auto-play")
async def toggle_auto_play(session_id: str, enabled: bool = True):
    """Enable/disable auto-play mode."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    session.set_auto_mode(enabled)
    
    return {"auto_play": enabled}


@app.get("/api/sessions/{session_id}/buttons")
async def get_action_buttons(session_id: str):
    """Get current action buttons."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    return {"buttons": session.get_action_buttons()}


@app.get("/api/sessions/{session_id}/map")
async def get_map(session_id: str):
    """Get explored map data."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    return {"rooms": session.get_map_data()}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Disconnect and delete a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    await session.disconnect()
    del sessions[session_id]
    
    return {"status": "disconnected"}


@app.post("/api/generate-image")
async def generate_image(request: ImageGenerationRequest):
    """Generate an image for a room using AI."""
    try:
        import replicate
        
        # Build prompt for Dune aesthetic
        prompt = f"""A cinematic scene from the Dune universe: {request.room_name}.
{request.description}
Setting: {request.area}, {request.environment}.
Style: Atmospheric, dramatic lighting, Dune film aesthetic, 
desert tones, vast scale, detailed architecture.
Cinematic wide shot, 4K quality, photorealistic."""
        
        # Use Replicate's SDXL
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": prompt,
                "negative_prompt": "cartoon, anime, low quality, blurry",
                "width": 1024,
                "height": 576,  # 16:9 aspect ratio
                "num_inference_steps": 30,
            }
        )
        
        if output and len(output) > 0:
            return {"image_url": output[0]}
        
        raise HTTPException(status_code=500, detail="Image generation failed")
        
    except ImportError:
        raise HTTPException(
            status_code=501, 
            detail="Image generation not available (replicate not installed)"
        )
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint for real-time communication
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket connection for real-time game updates."""
    await websocket.accept()
    
    # Get or create session
    if session_id not in sessions:
        await websocket.close(code=4004, reason="Session not found")
        return
    
    session = sessions[session_id]
    
    # Event queue for this WebSocket
    event_queue: asyncio.Queue = asyncio.Queue()
    
    # Register event handler
    def handle_event(event):
        event_queue.put_nowait({
            "type": event.type,
            "data": event.data,
            "timestamp": event.timestamp.isoformat(),
        })
    
    session.on_event(handle_event)
    
    try:
        # Create tasks for sending and receiving
        async def send_events():
            while True:
                event = await event_queue.get()
                await websocket.send_json(event)
        
        async def receive_commands():
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "command":
                    await session.send_command(data.get("command", ""))
                elif data.get("type") == "auto_play":
                    session.set_auto_mode(data.get("enabled", False))
                elif data.get("type") == "pause":
                    session.pause()
                elif data.get("type") == "resume":
                    session.resume()
        
        async def run_session():
            await session.run()
        
        # Run all tasks concurrently
        await asyncio.gather(
            send_events(),
            receive_commands(),
            run_session(),
        )
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Don't disconnect session, just remove event handler
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
