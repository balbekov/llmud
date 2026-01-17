#!/usr/bin/env python3
"""
Test script v2 - Debug GMCP negotiation in detail.
"""

import asyncio
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from llmud.telnet_client import TelnetClient, TelnetOption, TelnetCommand
import json

class GMCPDebugger:
    """Debug GMCP communication."""
    
    def __init__(self):
        self.telnet = TelnetClient("dunemud.net", 6789)
        self.gmcp_messages = []
        self.text_output = []
        
    async def _on_text(self, text: str) -> None:
        """Handle text."""
        self.text_output.append(text)
        # Print first line
        for line in text.split('\n')[:2]:
            import re
            clean = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line).strip()
            if clean:
                print(f"[TEXT] {clean[:80]}")
    
    async def _on_gmcp(self, module: str, data) -> None:
        """Handle GMCP."""
        self.gmcp_messages.append((module, data))
        print(f"[GMCP] {module}: {json.dumps(data) if isinstance(data, (dict, list)) else data}")
    
    async def run(self):
        """Run the debug test."""
        print("="*60)
        print("GMCP Debug Test")
        print("="*60)
        
        self.telnet.on_text(self._on_text)
        self.telnet.on_gmcp(self._on_gmcp)
        
        try:
            # Connect
            print("\n[1] Connecting...")
            if not await self.telnet.connect():
                print("FAILED to connect!")
                return
            print("Connected!")
            
            # Wait for negotiation
            print("\n[2] Waiting for GMCP negotiation...")
            await asyncio.sleep(3)
            
            # Receive initial data
            for _ in range(20):
                await self.telnet.receive()
                await asyncio.sleep(0.1)
            
            print(f"\n[3] GMCP Status: enabled={self.telnet.gmcp_enabled}")
            print(f"    Messages received so far: {len(self.gmcp_messages)}")
            
            # Try different GMCP module registration formats
            print("\n[4] Trying different GMCP module registrations...")
            
            # Method 1: Standard format
            print("    Sending Core.Supports.Set with standard format...")
            await self.telnet.send_gmcp("Core.Supports.Set", ["Room 1", "Char 1", "Comm 1"])
            await asyncio.sleep(1)
            for _ in range(10):
                await self.telnet.receive()
                await asyncio.sleep(0.1)
            
            # Method 2: Add individually
            print("    Sending Core.Supports.Add...")
            await self.telnet.send_gmcp("Core.Supports.Add", ["Room.Info 1"])
            await asyncio.sleep(0.5)
            await self.telnet.send_gmcp("Core.Supports.Add", ["Char.Vitals 1"])
            await asyncio.sleep(0.5)
            await self.telnet.send_gmcp("Core.Supports.Add", ["Char.Status 1"])
            await asyncio.sleep(0.5)
            
            for _ in range(10):
                await self.telnet.receive()
                await asyncio.sleep(0.1)
            
            # Method 3: Request Core.Hello first
            print("    Sending Core.Hello...")
            await self.telnet.send_gmcp("Core.Hello", {"client": "LLMUD", "version": "0.1"})
            await asyncio.sleep(1)
            
            for _ in range(10):
                await self.telnet.receive()
                await asyncio.sleep(0.1)
            
            print(f"\n[5] Messages after module registration: {len(self.gmcp_messages)}")
            
            # Login as guest
            print("\n[6] Logging in as guest...")
            await self.telnet.send("guest")
            await asyncio.sleep(2)
            
            for _ in range(20):
                await self.telnet.receive()
                await asyncio.sleep(0.1)
            
            # Press enter a few times to get through login prompts
            for _ in range(3):
                await self.telnet.send("")
                await asyncio.sleep(1)
                for _ in range(10):
                    await self.telnet.receive()
                    await asyncio.sleep(0.1)
            
            print(f"\n[7] Messages after login: {len(self.gmcp_messages)}")
            
            # Look around
            print("\n[8] Looking around...")
            await self.telnet.send("look")
            await asyncio.sleep(2)
            
            for _ in range(20):
                await self.telnet.receive()
                await asyncio.sleep(0.1)
            
            # Try moving
            print("\n[9] Moving north...")
            await self.telnet.send("n")
            await asyncio.sleep(2)
            
            for _ in range(20):
                await self.telnet.receive()
                await asyncio.sleep(0.1)
            
            # Try requesting room info explicitly
            print("\n[10] Requesting Room.Info explicitly...")
            await self.telnet.send_gmcp("Room.Info", {})
            await asyncio.sleep(1)
            
            for _ in range(10):
                await self.telnet.receive()
                await asyncio.sleep(0.1)
            
            # Final report
            print("\n" + "="*60)
            print("FINAL REPORT")
            print("="*60)
            print(f"GMCP Enabled: {self.telnet.gmcp_enabled}")
            print(f"Total GMCP Messages Received: {len(self.gmcp_messages)}")
            
            if self.gmcp_messages:
                print("\nGMCP Messages:")
                for module, data in self.gmcp_messages:
                    print(f"  {module}: {data}")
            else:
                print("\nNO GMCP messages received!")
                print("\nThis indicates:")
                print("  1. The server may not support GMCP data for these modules")
                print("  2. OR the GMCP module request format is incorrect")
                print("  3. OR GMCP data is only sent under certain conditions")
            
            # Check if we got any room info from text
            print("\n\nText output (looking for room names):")
            for text in self.text_output[-10:]:
                if '-[' in text and ']-' in text:
                    import re
                    match = re.search(r'-\[\s*(.+?)\s*\]-', text)
                    if match:
                        print(f"  Room from text: {match.group(1)}")
            
        finally:
            await self.telnet.disconnect()
            print("\nDisconnected.")


async def main():
    debugger = GMCPDebugger()
    await debugger.run()


if __name__ == "__main__":
    asyncio.run(main())
