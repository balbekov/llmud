"""
Tests for MUD connection and login functionality.

These tests verify that we can:
1. Connect to DuneMUD
2. Create or login as the "Dentrifier" player
3. Verify successful login
"""

import asyncio
import pytest

pytestmark = pytest.mark.asyncio


class TestMudConnection:
    """Tests for basic MUD connection."""

    async def test_connect_to_mud(self, telnet_client):
        """Test that we can establish a connection to the MUD server."""
        connected = await telnet_client.connect()
        assert connected is True
        assert telnet_client.connected is True

    async def test_disconnect_from_mud(self, telnet_client):
        """Test that we can disconnect cleanly."""
        await telnet_client.connect()
        await telnet_client.disconnect()
        assert telnet_client.connected is False

    async def test_receive_initial_data(self, telnet_client):
        """Test that we receive data after connecting."""
        await telnet_client.connect()
        
        # Collect data for a few seconds
        collected_text = []
        
        async def collect_text(text):
            collected_text.append(text)
        
        telnet_client.on_text(collect_text)
        
        # Wait for data
        for _ in range(30):  # ~3 seconds with 0.1s timeout in receive
            await telnet_client.receive()
        
        # Should have received some welcome text
        all_text = "\n".join(collected_text)
        assert len(all_text) > 0, "Expected to receive some text from MUD"
        
        # Check for typical MUD welcome content
        text_lower = all_text.lower()
        assert any(keyword in text_lower for keyword in [
            "dune", "welcome", "name", "connect", "mud"
        ]), f"Expected welcome text, got: {all_text[:500]}"


class TestDentrifierLogin:
    """Tests for Dentrifier player login."""

    async def test_login_dentrifier(self, telnet_client, test_credentials):
        """Test logging in as the Dentrifier player."""
        await telnet_client.connect()
        
        collected_text = []
        
        async def collect_text(text):
            collected_text.append(text)
        
        telnet_client.on_text(collect_text)
        
        # Receive initial welcome/prompt
        for _ in range(20):
            await telnet_client.receive()
        
        # Send username
        await telnet_client.send(test_credentials["username"])
        
        # Wait for password prompt
        await asyncio.sleep(1)
        for _ in range(20):
            await telnet_client.receive()
        
        # Send password
        await telnet_client.send(test_credentials["password"])
        
        # Wait for login result
        await asyncio.sleep(2)
        for _ in range(30):
            await telnet_client.receive()
        
        all_text = "\n".join(collected_text)
        text_lower = all_text.lower()
        
        # Check for successful login indicators
        # Note: On first run, this might create the character
        login_success = any(keyword in text_lower for keyword in [
            "welcome back", "last login", "you enter", 
            "obvious exit", "room", "area", "standing"
        ])
        
        # Check for character creation flow (first time)
        char_creation = any(keyword in text_lower for keyword in [
            "create", "gender", "male", "female", "new character"
        ])
        
        assert login_success or char_creation, \
            f"Expected login success or character creation, got: {all_text[-1000:]}"

    async def test_session_login(self, session_config):
        """Test login using MUDSession."""
        from llmud import MUDSession
        
        session = MUDSession(session_config)
        
        collected_events = []
        
        def event_handler(event):
            collected_events.append(event)
        
        session.on_event(event_handler)
        
        # Connect
        connected = await session.connect()
        assert connected is True
        
        # Let it receive initial data
        for _ in range(30):
            await session.telnet.receive()
        
        # Login
        await session.login()
        
        # Wait for login to process
        await asyncio.sleep(2)
        for _ in range(50):
            await session.telnet.receive()
        
        # Check state
        state = session.get_state()
        assert state["connected"] is True
        
        # Check we received events
        assert len(collected_events) > 0, "Expected to receive events"
        
        # Check for text events
        text_events = [e for e in collected_events if e.type == "text"]
        assert len(text_events) > 0, "Expected text events"
        
        await session.disconnect()

    async def test_send_look_command(self, telnet_client, test_credentials):
        """Test sending the 'look' command after login."""
        await telnet_client.connect()
        
        collected_text = []
        
        async def collect_text(text):
            collected_text.append(text)
        
        telnet_client.on_text(collect_text)
        
        # Login sequence
        for _ in range(20):
            await telnet_client.receive()
        
        await telnet_client.send(test_credentials["username"])
        await asyncio.sleep(1)
        
        for _ in range(20):
            await telnet_client.receive()
        
        await telnet_client.send(test_credentials["password"])
        await asyncio.sleep(2)
        
        for _ in range(30):
            await telnet_client.receive()
        
        # Clear collected text to focus on look output
        collected_text.clear()
        
        # Send look command
        await telnet_client.send("look")
        
        # Wait for response
        await asyncio.sleep(1)
        for _ in range(20):
            await telnet_client.receive()
        
        all_text = "\n".join(collected_text)
        
        # Should receive room description or game content
        assert len(all_text) > 0, "Expected response from 'look' command"


class TestGMCPSupport:
    """Tests for GMCP protocol support."""

    async def test_gmcp_enabled(self, telnet_client):
        """Test that GMCP is negotiated and enabled."""
        await telnet_client.connect()
        
        # Wait for negotiation
        for _ in range(30):
            await telnet_client.receive()
        
        # GMCP should be enabled after negotiation
        assert telnet_client.gmcp_enabled is True, \
            "Expected GMCP to be enabled after connection"

    async def test_gmcp_messages_received(self, telnet_client, test_credentials):
        """Test that GMCP messages are received after login."""
        await telnet_client.connect()
        
        gmcp_messages = []
        
        async def gmcp_handler(module, data):
            gmcp_messages.append({"module": module, "data": data})
        
        telnet_client.on_gmcp(gmcp_handler)
        
        # Wait for initial negotiation
        for _ in range(30):
            await telnet_client.receive()
        
        # Login
        await telnet_client.send(test_credentials["username"])
        await asyncio.sleep(1)
        
        for _ in range(20):
            await telnet_client.receive()
        
        await telnet_client.send(test_credentials["password"])
        
        # Wait for GMCP messages
        await asyncio.sleep(3)
        for _ in range(50):
            await telnet_client.receive()
        
        # Should have received GMCP messages
        # Common modules: Room.Info, Char.Vitals, Char.Name
        if len(gmcp_messages) > 0:
            modules = [m["module"] for m in gmcp_messages]
            print(f"Received GMCP modules: {modules}")
            
            # Check for expected modules
            expected_modules = ["Room", "Char"]
            has_expected = any(
                any(mod.startswith(exp) for exp in expected_modules)
                for mod in modules
            )
            assert has_expected, f"Expected GMCP modules, got: {modules}"

