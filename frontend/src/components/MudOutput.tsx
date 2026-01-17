import React, { useEffect, useRef } from 'react';
import { useGameStore } from '../store/gameStore';

// Parse ANSI escape codes and convert to HTML
function parseAnsi(text: string): string {
  // Simple ANSI parser - extend as needed
  const ansiRegex = /\x1b\[(\d+(?:;\d+)*)m/g;
  
  let result = text;
  let currentClasses: string[] = [];
  
  result = result.replace(ansiRegex, (_match, codes) => {
    const codeList = codes.split(';').map(Number);
    const newClasses: string[] = [];
    
    for (const code of codeList) {
      switch (code) {
        case 0: // Reset
          currentClasses = [];
          break;
        case 1: // Bold
          newClasses.push('ansi-bold');
          break;
        case 4: // Underline
          newClasses.push('ansi-underline');
          break;
        case 30: newClasses.push('ansi-black'); break;
        case 31: newClasses.push('ansi-red'); break;
        case 32: newClasses.push('ansi-green'); break;
        case 33: newClasses.push('ansi-yellow'); break;
        case 34: newClasses.push('ansi-blue'); break;
        case 35: newClasses.push('ansi-magenta'); break;
        case 36: newClasses.push('ansi-cyan'); break;
        case 37: newClasses.push('ansi-white'); break;
        case 90: newClasses.push('ansi-bright-black'); break;
        case 91: newClasses.push('ansi-bright-red'); break;
        case 92: newClasses.push('ansi-bright-green'); break;
        case 93: newClasses.push('ansi-bright-yellow'); break;
        case 94: newClasses.push('ansi-bright-blue'); break;
        case 95: newClasses.push('ansi-bright-magenta'); break;
        case 96: newClasses.push('ansi-bright-cyan'); break;
        case 97: newClasses.push('ansi-bright-white'); break;
      }
    }
    
    currentClasses = [...currentClasses, ...newClasses];
    
    if (currentClasses.length > 0) {
      return `</span><span class="${currentClasses.join(' ')}">`;
    }
    return '</span><span>';
  });
  
  return `<span>${result}</span>`;
}

export const MudOutput: React.FC = () => {
  const messages = useGameStore((state) => state.messages);
  const outputRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll to bottom
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [messages]);
  
  return (
    <div 
      ref={outputRef}
      className="h-full overflow-y-auto bg-gray-900 p-4 font-mono text-sm"
    >
      {messages.map((msg) => (
        <div 
          key={msg.id}
          className={`mud-output ${
            msg.type === 'system' ? 'text-yellow-400' :
            msg.type === 'chat' ? 'text-cyan-400' :
            msg.type === 'combat' ? 'text-red-400' :
            'text-gray-200'
          }`}
          dangerouslySetInnerHTML={{ __html: parseAnsi(msg.text) }}
        />
      ))}
    </div>
  );
};
