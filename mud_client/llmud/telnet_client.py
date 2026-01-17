"""
Telnet Client with GMCP Support for MUD connections.
"""

import asyncio
import re
import json
import logging
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)


class TelnetOption(IntEnum):
    """Telnet option codes."""
    ECHO = 1
    SGA = 3  # Suppress Go Ahead
    TTYPE = 24  # Terminal Type
    NAWS = 31  # Negotiate About Window Size
    GMCP = 201  # Generic MUD Communication Protocol


class TelnetCommand(IntEnum):
    """Telnet command codes."""
    SE = 240  # Subnegotiation End
    NOP = 241  # No Operation
    DM = 242  # Data Mark
    BRK = 243  # Break
    IP = 244  # Interrupt Process
    AO = 245  # Abort Output
    AYT = 246  # Are You There
    EC = 247  # Erase Character
    EL = 248  # Erase Line
    GA = 249  # Go Ahead
    SB = 250  # Subnegotiation Begin
    WILL = 251
    WONT = 252
    DO = 253
    DONT = 254
    IAC = 255  # Interpret As Command


@dataclass
class TelnetState:
    """Tracks telnet negotiation state."""
    gmcp_enabled: bool = False
    echo_enabled: bool = True
    sga_enabled: bool = False
    ttype_enabled: bool = False


class TelnetClient:
    """Async telnet client with GMCP support for MUD connections."""

    def __init__(
        self,
        host: str = "dunemud.net",
        port: int = 6789,
        encoding: str = "utf-8",
    ):
        self.host = host
        self.port = port
        self.encoding = encoding
        
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._state = TelnetState()
        
        # Callbacks
        self._text_callback: Optional[Callable[[str], Any]] = None
        self._gmcp_callback: Optional[Callable[[str, Any], Any]] = None
        
        # Buffers
        self._receive_buffer = bytearray()
        self._text_buffer = ""
        
    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def gmcp_enabled(self) -> bool:
        return self._state.gmcp_enabled

    def on_text(self, callback: Callable[[str], Any]) -> None:
        """Register callback for received text."""
        self._text_callback = callback

    def on_gmcp(self, callback: Callable[[str, Any], Any]) -> None:
        """Register callback for GMCP messages."""
        self._gmcp_callback = callback

    async def connect(self) -> bool:
        """Connect to the MUD server."""
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.host, self.port
            )
            self._connected = True
            logger.info(f"Connected to {self.host}:{self.port}")
            
            # Request GMCP support
            await self._send_will(TelnetOption.GMCP)
            await self._send_do(TelnetOption.GMCP)
            
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from the server."""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False
        self._reader = None
        self._writer = None
        logger.info("Disconnected")

    async def send(self, text: str) -> None:
        """Send a command to the MUD."""
        if not self._connected or not self._writer:
            raise ConnectionError("Not connected to server")
        
        # Escape any IAC bytes in the text
        data = text.encode(self.encoding)
        data = data.replace(bytes([TelnetCommand.IAC]), bytes([TelnetCommand.IAC, TelnetCommand.IAC]))
        
        # Add newline if not present
        if not data.endswith(b'\n'):
            data += b'\n'
        
        self._writer.write(data)
        await self._writer.drain()
        logger.debug(f"Sent: {text}")

    async def send_gmcp(self, module: str, data: Any = None) -> None:
        """Send a GMCP message."""
        if not self._state.gmcp_enabled:
            logger.warning("GMCP not enabled, cannot send GMCP message")
            return
        
        if data is not None:
            message = f"{module} {json.dumps(data)}"
        else:
            message = module
        
        payload = bytes([
            TelnetCommand.IAC, TelnetCommand.SB, TelnetOption.GMCP
        ]) + message.encode(self.encoding) + bytes([
            TelnetCommand.IAC, TelnetCommand.SE
        ])
        
        if self._writer:
            self._writer.write(payload)
            await self._writer.drain()
            logger.debug(f"Sent GMCP: {module}")

    async def enable_gmcp_modules(self, modules: list[str]) -> None:
        """Enable specific GMCP modules."""
        for module in modules:
            await self.send_gmcp("Core.Supports.Set", [f"{module} 1"])

    async def receive(self) -> Optional[str]:
        """Receive and process data from the server."""
        if not self._connected or not self._reader:
            return None
        
        try:
            data = await asyncio.wait_for(
                self._reader.read(4096),
                timeout=0.1
            )
            if not data:
                self._connected = False
                return None
            
            self._receive_buffer.extend(data)
            return await self._process_buffer()
            
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Receive error: {e}")
            self._connected = False
            return None

    async def _process_buffer(self) -> str:
        """Process the receive buffer, handling telnet commands."""
        text_output = ""
        i = 0
        
        while i < len(self._receive_buffer):
            byte = self._receive_buffer[i]
            
            if byte == TelnetCommand.IAC:
                if i + 1 >= len(self._receive_buffer):
                    break  # Wait for more data
                
                cmd = self._receive_buffer[i + 1]
                
                if cmd == TelnetCommand.IAC:
                    # Escaped IAC
                    text_output += chr(TelnetCommand.IAC)
                    i += 2
                    
                elif cmd in (TelnetCommand.WILL, TelnetCommand.WONT, 
                           TelnetCommand.DO, TelnetCommand.DONT):
                    if i + 2 >= len(self._receive_buffer):
                        break  # Wait for more data
                    
                    option = self._receive_buffer[i + 2]
                    await self._handle_negotiation(cmd, option)
                    i += 3
                    
                elif cmd == TelnetCommand.SB:
                    # Subnegotiation
                    se_pos = self._find_subneg_end(i + 2)
                    if se_pos == -1:
                        break  # Wait for more data
                    
                    subneg_data = bytes(self._receive_buffer[i + 2:se_pos])
                    await self._handle_subnegotiation(subneg_data)
                    i = se_pos + 2  # Skip IAC SE
                    
                elif cmd in (TelnetCommand.GA, TelnetCommand.NOP):
                    i += 2
                    
                else:
                    i += 2
            else:
                text_output += chr(byte)
                i += 1
        
        # Remove processed bytes from buffer
        self._receive_buffer = self._receive_buffer[i:]
        
        # Clean up text output
        if text_output:
            # Remove ANSI escape codes for cleaner processing
            # But keep them for the frontend display
            self._text_buffer += text_output
            
            # Process complete lines
            if '\n' in self._text_buffer:
                lines = self._text_buffer.split('\n')
                complete_text = '\n'.join(lines[:-1])
                self._text_buffer = lines[-1]
                
                if self._text_callback and complete_text:
                    await self._invoke_callback(self._text_callback, complete_text)
                
                return complete_text
        
        return ""

    def _find_subneg_end(self, start: int) -> int:
        """Find the end of a subnegotiation sequence."""
        i = start
        while i < len(self._receive_buffer) - 1:
            if (self._receive_buffer[i] == TelnetCommand.IAC and 
                self._receive_buffer[i + 1] == TelnetCommand.SE):
                return i
            i += 1
        return -1

    async def _handle_negotiation(self, command: int, option: int) -> None:
        """Handle telnet option negotiation."""
        if option == TelnetOption.GMCP:
            if command == TelnetCommand.WILL or command == TelnetCommand.DO:
                self._state.gmcp_enabled = True
                logger.info("GMCP enabled")
                if command == TelnetCommand.WILL:
                    await self._send_do(option)
                else:
                    await self._send_will(option)
                    
                # Enable desired GMCP modules
                await self.enable_gmcp_modules([
                    "Char",
                    "Room", 
                    "Comm.Channel",
                    "Guild"
                ])
            else:
                self._state.gmcp_enabled = False
                
        elif option == TelnetOption.ECHO:
            if command == TelnetCommand.WILL:
                self._state.echo_enabled = False
                await self._send_do(option)
            elif command == TelnetCommand.WONT:
                self._state.echo_enabled = True
                await self._send_dont(option)
                
        elif option == TelnetOption.SGA:
            if command == TelnetCommand.WILL:
                self._state.sga_enabled = True
                await self._send_do(option)
                
        elif option == TelnetOption.TTYPE:
            if command == TelnetCommand.DO:
                self._state.ttype_enabled = True
                await self._send_will(option)

    async def _handle_subnegotiation(self, data: bytes) -> None:
        """Handle telnet subnegotiation."""
        if not data:
            return
            
        option = data[0]
        
        if option == TelnetOption.GMCP:
            await self._process_gmcp(data[1:])
        elif option == TelnetOption.TTYPE:
            if len(data) > 1 and data[1] == 1:  # SEND request
                await self._send_ttype()

    async def _process_gmcp(self, data: bytes) -> None:
        """Process a GMCP message."""
        try:
            message = data.decode(self.encoding)
            
            # Parse module and data
            space_pos = message.find(' ')
            if space_pos == -1:
                module = message
                gmcp_data = None
            else:
                module = message[:space_pos]
                json_str = message[space_pos + 1:]
                try:
                    gmcp_data = json.loads(json_str)
                except json.JSONDecodeError:
                    gmcp_data = json_str
            
            logger.debug(f"GMCP received: {module} = {gmcp_data}")
            
            if self._gmcp_callback:
                await self._invoke_callback(self._gmcp_callback, module, gmcp_data)
                
        except Exception as e:
            logger.error(f"GMCP parse error: {e}")

    async def _invoke_callback(self, callback: Callable, *args) -> None:
        """Invoke a callback, handling both sync and async functions."""
        result = callback(*args)
        if asyncio.iscoroutine(result):
            await result

    async def _send_will(self, option: int) -> None:
        """Send WILL negotiation."""
        if self._writer:
            self._writer.write(bytes([TelnetCommand.IAC, TelnetCommand.WILL, option]))
            await self._writer.drain()

    async def _send_wont(self, option: int) -> None:
        """Send WONT negotiation."""
        if self._writer:
            self._writer.write(bytes([TelnetCommand.IAC, TelnetCommand.WONT, option]))
            await self._writer.drain()

    async def _send_do(self, option: int) -> None:
        """Send DO negotiation."""
        if self._writer:
            self._writer.write(bytes([TelnetCommand.IAC, TelnetCommand.DO, option]))
            await self._writer.drain()

    async def _send_dont(self, option: int) -> None:
        """Send DONT negotiation."""
        if self._writer:
            self._writer.write(bytes([TelnetCommand.IAC, TelnetCommand.DONT, option]))
            await self._writer.drain()

    async def _send_ttype(self) -> None:
        """Send terminal type information."""
        ttype = b"XTERM-256COLOR"
        payload = bytes([
            TelnetCommand.IAC, TelnetCommand.SB, TelnetOption.TTYPE, 0
        ]) + ttype + bytes([
            TelnetCommand.IAC, TelnetCommand.SE
        ])
        if self._writer:
            self._writer.write(payload)
            await self._writer.drain()
