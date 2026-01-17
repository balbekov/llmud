import { useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { createSession, createWebSocket } from '../api/client';
import { Loader2, Power, PowerOff, Bot, BotOff } from 'lucide-react';

export const ConnectionPanel: React.FC = () => {
  const [host, setHost] = useState('dunemud.net');
  const [port, setPort] = useState(6789);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [llmProvider, setLlmProvider] = useState('anthropic');
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const connected = useGameStore((state) => state.connected);
  const autoPlay = useGameStore((state) => state.autoPlay);
  
  const setConnected = useGameStore((state) => state.setConnected);
  const setSessionId = useGameStore((state) => state.setSessionId);
  const setAutoPlay = useGameStore((state) => state.setAutoPlay);
  const addMessage = useGameStore((state) => state.addMessage);
  const setCurrentRoom = useGameStore((state) => state.setCurrentRoom);
  const setCharacter = useGameStore((state) => state.setCharacter);
  const reset = useGameStore((state) => state.reset);
  
  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    
    try {
      // Create session via REST API
      const result = await createSession({
        host,
        port,
        username,
        password,
        llm_provider: llmProvider,
        auto_play: false,
      });
      
      setSessionId(result.session_id);
      setConnected(true);
      
      // Connect WebSocket for real-time updates
      const ws = createWebSocket(result.session_id);
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      };
      
      ws.onclose = () => {
        addMessage('Disconnected from server', 'system');
        setConnected(false);
      };
      
      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        addMessage('Connection error', 'system');
      };
      
      addMessage('Connected to ' + host, 'system');
      
    } catch (err: any) {
      console.error('Connection failed:', err);
      setError(err.message || 'Failed to connect');
    } finally {
      setConnecting(false);
    }
  };
  
  const handleWebSocketMessage = (data: any) => {
    switch (data.type) {
      case 'text':
        addMessage(data.data.text, 'text');
        break;
        
      case 'state_change':
        if (data.data.type === 'vitals' || data.data.type === 'room') {
          // Update character and room from GMCP
          if (data.data.data.character) {
            setCharacter({
              name: data.data.data.character.name || '',
              guild: data.data.data.character.guild || 'none',
              level: data.data.data.character.level || 1,
              money: data.data.data.character.money || 0,
              bank: data.data.data.character.bank || 0,
              wimpy: data.data.data.character.wimpy || 0,
              vitals: {
                hp: parseInt(data.data.data.character.hp?.split('/')[0]) || 0,
                maxhp: parseInt(data.data.data.character.hp?.split('/')[1]) || 1,
                cp: parseInt(data.data.data.character.cp?.split('/')[0]) || 0,
                maxcp: parseInt(data.data.data.character.cp?.split('/')[1]) || 1,
                hp_percent: data.data.data.character.hp_percent || 0,
                cp_percent: data.data.data.character.cp_percent || 0,
              },
              stats: data.data.data.stats || {
                str: 0, con: 0, int: 0, wis: 0, dex: 0, qui: 0
              },
            });
          }
          if (data.data.data.room) {
            setCurrentRoom({
              name: data.data.data.room.name || 'Unknown',
              area: data.data.data.room.area || 'unknown',
              environment: data.data.data.room.environment || 'unknown',
              exits: data.data.data.room.exits || [],
            });
          }
        }
        break;
        
      case 'chat':
        addMessage(`[${data.data.channel}] ${data.data.talker}: ${data.data.text}`, 'chat');
        break;
        
      case 'ai_action':
        addMessage(`AI: ${data.data.command}`, 'system');
        break;
        
      case 'error':
        addMessage(`Error: ${data.data.message}`, 'system');
        break;
    }
  };
  
  const handleDisconnect = () => {
    reset();
    addMessage('Disconnected', 'system');
  };
  
  const toggleAutoPlay = () => {
    setAutoPlay(!autoPlay);
    addMessage(autoPlay ? 'Auto-play disabled' : 'Auto-play enabled', 'system');
  };
  
  if (connected) {
    return (
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
            <span className="text-green-400 font-medium">Connected</span>
          </div>
          <button
            onClick={handleDisconnect}
            className="btn btn-danger text-sm flex items-center gap-1"
          >
            <PowerOff size={16} />
            Disconnect
          </button>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={toggleAutoPlay}
            className={`btn flex items-center gap-2 ${
              autoPlay ? 'btn-primary' : 'btn-secondary'
            }`}
          >
            {autoPlay ? <Bot size={16} /> : <BotOff size={16} />}
            {autoPlay ? 'Auto-Play ON' : 'Auto-Play OFF'}
          </button>
          <span className="text-sm text-gray-400">
            {autoPlay ? 'AI is playing' : 'Manual control'}
          </span>
        </div>
      </div>
    );
  }
  
  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-white mb-4">Connect to DuneMUD</h3>
      
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm text-gray-400">Host</label>
            <input
              type="text"
              value={host}
              onChange={(e) => setHost(e.target.value)}
              className="input w-full"
            />
          </div>
          <div>
            <label className="text-sm text-gray-400">Port</label>
            <input
              type="number"
              value={port}
              onChange={(e) => setPort(parseInt(e.target.value))}
              className="input w-full"
            />
          </div>
        </div>
        
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm text-gray-400">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="input w-full"
              placeholder="Optional"
            />
          </div>
          <div>
            <label className="text-sm text-gray-400">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input w-full"
              placeholder="Optional"
            />
          </div>
        </div>
        
        <div>
          <label className="text-sm text-gray-400">LLM Provider</label>
          <select
            value={llmProvider}
            onChange={(e) => setLlmProvider(e.target.value)}
            className="input w-full"
          >
            <option value="anthropic">Anthropic (Claude)</option>
            <option value="openai">OpenAI (GPT-4)</option>
          </select>
        </div>
        
        {error && (
          <div className="text-red-400 text-sm">{error}</div>
        )}
        
        <button
          onClick={handleConnect}
          disabled={connecting}
          className="btn btn-primary w-full flex items-center justify-center gap-2"
        >
          {connecting ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Connecting...
            </>
          ) : (
            <>
              <Power size={16} />
              Connect
            </>
          )}
        </button>
      </div>
    </div>
  );
};
