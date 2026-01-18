"""
Pytest configuration and fixtures for LLMUD tests.
"""

import os
import sys
import asyncio
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "mud_client"))
sys.path.insert(0, str(project_root / "backend"))

# Load environment variables from .env file
load_dotenv(project_root / ".env")

from llmud import TelnetClient, MUDSession, SessionConfig, LLMAgent


# Test configuration
TEST_MUD_HOST = "dunemud.net"
TEST_MUD_PORT = 6789
TEST_USERNAME = "Dentrifier"
TEST_PASSWORD = "Dentrifier"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mud_host():
    """Return the MUD host."""
    return TEST_MUD_HOST


@pytest.fixture
def mud_port():
    """Return the MUD port."""
    return TEST_MUD_PORT


@pytest.fixture
def test_credentials():
    """Return test credentials."""
    return {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    }


@pytest.fixture
async def telnet_client(mud_host, mud_port):
    """Create a telnet client fixture."""
    client = TelnetClient(host=mud_host, port=mud_port)
    yield client
    if client.connected:
        await client.disconnect()


@pytest.fixture
def session_config(mud_host, mud_port, test_credentials):
    """Create a session config fixture."""
    return SessionConfig(
        host=mud_host,
        port=mud_port,
        username=test_credentials["username"],
        password=test_credentials["password"],
        llm_provider="openai",
        llm_api_key=os.getenv("OPENAI_API_KEY", ""),
        strategy_path=str(Path(__file__).parent.parent / "strategy.md"),
    )


@pytest.fixture
async def mud_session(session_config):
    """Create a MUD session fixture."""
    session = MUDSession(session_config)
    yield session
    if session.telnet.connected:
        await session.disconnect()


@pytest.fixture
def openai_api_key():
    """Return OpenAI API key from environment."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set in environment")
    return key


@pytest.fixture
def anthropic_api_key():
    """Return Anthropic API key from environment."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set in environment")
    return key


@pytest.fixture
def loop_strategy_path():
    """Return path to the loop strategy file."""
    return str(Path(__file__).parent / "strategies" / "loop_strategy.md")


@pytest.fixture
def loop_session_config(mud_host, mud_port, test_credentials, loop_strategy_path):
    """Create a session config with the loop strategy."""
    return SessionConfig(
        host=mud_host,
        port=mud_port,
        username=test_credentials["username"],
        password=test_credentials["password"],
        llm_provider="openai",
        llm_api_key=os.getenv("OPENAI_API_KEY", ""),
        strategy_path=loop_strategy_path,
    )

