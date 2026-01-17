import React, { useState, useRef, useEffect } from 'react';
import { useGameStore } from '../store/gameStore';
import { sendCommand } from '../api/client';
import { Send } from 'lucide-react';

export const CommandInput: React.FC = () => {
  const [command, setCommand] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const sessionId = useGameStore((state) => state.sessionId);
  const commandHistory = useGameStore((state) => state.commandHistory);
  const historyIndex = useGameStore((state) => state.historyIndex);
  const addCommandToHistory = useGameStore((state) => state.addCommandToHistory);
  const setHistoryIndex = useGameStore((state) => state.setHistoryIndex);
  const addMessage = useGameStore((state) => state.addMessage);
  
  useEffect(() => {
    inputRef.current?.focus();
  }, []);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!command.trim() || !sessionId) return;
    
    try {
      // Add to history
      addCommandToHistory(command);
      
      // Show command in output
      addMessage(`> ${command}`, 'system');
      
      // Send command
      await sendCommand(sessionId, command);
      
      // Clear input
      setCommand('');
    } catch (error) {
      console.error('Failed to send command:', error);
      addMessage('Error sending command', 'system');
    }
  };
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (commandHistory.length > 0) {
        const newIndex = historyIndex < commandHistory.length - 1 
          ? historyIndex + 1 
          : historyIndex;
        setHistoryIndex(newIndex);
        setCommand(commandHistory[commandHistory.length - 1 - newIndex] || '');
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1;
        setHistoryIndex(newIndex);
        setCommand(commandHistory[commandHistory.length - 1 - newIndex] || '');
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setCommand('');
      }
    }
  };
  
  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        ref={inputRef}
        type="text"
        value={command}
        onChange={(e) => setCommand(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Enter command..."
        className="flex-1 input bg-gray-800 border-gray-700 text-white"
        autoComplete="off"
        spellCheck="false"
      />
      <button
        type="submit"
        className="btn btn-primary flex items-center gap-2"
        disabled={!sessionId}
      >
        <Send size={16} />
        Send
      </button>
    </form>
  );
};
