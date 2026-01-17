import React from 'react';
import { useGameStore, type ActionButton } from '../store/gameStore';
import { sendCommand } from '../api/client';
import { 
  ArrowUp, ArrowDown, ArrowLeft, ArrowRight, 
  ArrowUpLeft, ArrowUpRight, ArrowDownLeft, ArrowDownRight,
  Eye, User, Swords, Package, LogOut, Info
} from 'lucide-react';

const directionIcons: Record<string, React.ReactNode> = {
  'n': <ArrowUp size={16} />,
  'north': <ArrowUp size={16} />,
  's': <ArrowDown size={16} />,
  'south': <ArrowDown size={16} />,
  'e': <ArrowRight size={16} />,
  'east': <ArrowRight size={16} />,
  'w': <ArrowLeft size={16} />,
  'west': <ArrowLeft size={16} />,
  'ne': <ArrowUpRight size={16} />,
  'northeast': <ArrowUpRight size={16} />,
  'nw': <ArrowUpLeft size={16} />,
  'northwest': <ArrowUpLeft size={16} />,
  'se': <ArrowDownRight size={16} />,
  'southeast': <ArrowDownRight size={16} />,
  'sw': <ArrowDownLeft size={16} />,
  'southwest': <ArrowDownLeft size={16} />,
  'u': <ArrowUp size={16} />,
  'up': <ArrowUp size={16} />,
  'd': <ArrowDown size={16} />,
  'down': <ArrowDown size={16} />,
};

const typeIcons: Record<string, React.ReactNode> = {
  'info': <Info size={16} />,
  'combat': <Swords size={16} />,
  'interaction': <User size={16} />,
};

interface ActionButtonProps {
  button: ActionButton;
  onClick: (command: string) => void;
}

const ActionButtonComponent: React.FC<ActionButtonProps> = ({ button, onClick }) => {
  const getIcon = () => {
    const lowerCmd = button.command.toLowerCase();
    if (directionIcons[lowerCmd]) return directionIcons[lowerCmd];
    if (button.command === 'look' || button.command === 'l') return <Eye size={16} />;
    if (button.command === 'i' || button.command === 'inventory') return <Package size={16} />;
    if (button.command === 'flee') return <LogOut size={16} />;
    if (typeIcons[button.type]) return typeIcons[button.type];
    return null;
  };
  
  const getButtonStyle = () => {
    switch (button.type) {
      case 'navigation':
        return 'bg-blue-600 hover:bg-blue-700';
      case 'combat':
        return 'bg-red-600 hover:bg-red-700';
      case 'interaction':
        return 'bg-green-600 hover:bg-green-700';
      default:
        return 'bg-gray-600 hover:bg-gray-700';
    }
  };
  
  return (
    <button
      onClick={() => onClick(button.command)}
      className={`px-3 py-2 rounded font-medium text-white transition-colors flex items-center gap-2 ${getButtonStyle()}`}
    >
      {getIcon()}
      <span>{button.label}</span>
    </button>
  );
};

export const ActionButtons: React.FC = () => {
  const actionButtons = useGameStore((state) => state.actionButtons);
  const sessionId = useGameStore((state) => state.sessionId);
  const currentRoom = useGameStore((state) => state.currentRoom);
  const addMessage = useGameStore((state) => state.addMessage);
  
  // Create navigation buttons from room exits
  const navigationButtons: ActionButton[] = currentRoom?.exits.map(exit => ({
    label: exit.toUpperCase(),
    command: exit,
    type: 'navigation' as const,
  })) || [];
  
  // Standard action buttons
  const standardButtons: ActionButton[] = [
    { label: 'Look', command: 'look', type: 'info' },
    { label: 'Score', command: 'score', type: 'info' },
    { label: 'Inventory', command: 'i', type: 'info' },
  ];
  
  const allButtons = [...navigationButtons, ...actionButtons, ...standardButtons];
  
  const handleClick = async (command: string) => {
    if (!sessionId) return;
    
    try {
      addMessage(`> ${command}`, 'system');
      await sendCommand(sessionId, command);
    } catch (error) {
      console.error('Failed to send command:', error);
    }
  };
  
  return (
    <div className="flex flex-wrap gap-2">
      {allButtons.map((button, index) => (
        <ActionButtonComponent
          key={`${button.command}-${index}`}
          button={button}
          onClick={handleClick}
        />
      ))}
    </div>
  );
};
