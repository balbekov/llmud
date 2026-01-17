import React from 'react';
import { useGameStore } from '../store/gameStore';
import { Heart, Zap, Wallet, Shield, Swords, User } from 'lucide-react';

const ProgressBar: React.FC<{
  value: number;
  max: number;
  color: string;
  label: string;
  icon: React.ReactNode;
}> = ({ value, max, color, label, icon }) => {
  const percent = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  
  return (
    <div className="flex items-center gap-2">
      <div className="text-gray-400">{icon}</div>
      <div className="flex-1">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-400">{label}</span>
          <span className="text-white">{value}/{max}</span>
        </div>
        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full ${color} transition-all duration-300`}
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>
    </div>
  );
};

export const PlayerStatus: React.FC = () => {
  const character = useGameStore((state) => state.character);
  const inCombat = useGameStore((state) => state.inCombat);
  const currentRoom = useGameStore((state) => state.currentRoom);
  
  if (!character) {
    return (
      <div className="card text-center text-gray-400">
        <User size={32} className="mx-auto mb-2" />
        <p>Not connected</p>
      </div>
    );
  }
  
  return (
    <div className="card space-y-4">
      {/* Character Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">{character.name}</h3>
          <p className="text-sm text-gray-400">
            Level {character.level} {character.guild}
          </p>
        </div>
        {inCombat && (
          <div className="flex items-center gap-1 text-red-500">
            <Swords size={20} />
            <span className="text-sm font-medium">Combat</span>
          </div>
        )}
      </div>
      
      {/* Vitals */}
      <div className="space-y-3">
        <ProgressBar
          value={character.vitals.hp}
          max={character.vitals.maxhp}
          color={character.vitals.hp_percent > 50 ? 'bg-green-500' : 
                 character.vitals.hp_percent > 25 ? 'bg-yellow-500' : 'bg-red-500'}
          label="HP"
          icon={<Heart size={16} />}
        />
        
        <ProgressBar
          value={character.vitals.cp}
          max={character.vitals.maxcp}
          color="bg-blue-500"
          label="CP"
          icon={<Zap size={16} />}
        />
      </div>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-2 text-center">
        {Object.entries(character.stats).map(([stat, value]) => (
          <div key={stat} className="bg-gray-700/50 rounded p-2">
            <div className="text-xs text-gray-400 uppercase">{stat}</div>
            <div className="text-lg font-medium text-white">{value}</div>
          </div>
        ))}
      </div>
      
      {/* Money */}
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2 text-yellow-400">
          <Wallet size={16} />
          <span>Solaris: {character.money.toLocaleString()}</span>
        </div>
        <span className="text-gray-400">
          Bank: {character.bank.toLocaleString()}
        </span>
      </div>
      
      {/* Wimpy */}
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2 text-gray-400">
          <Shield size={16} />
          <span>Wimpy</span>
        </div>
        <span className="text-white">{character.wimpy}%</span>
      </div>
      
      {/* Current Location */}
      {currentRoom && (
        <div className="pt-2 border-t border-gray-700">
          <div className="text-sm text-gray-400">Location</div>
          <div className="text-white font-medium">{currentRoom.name}</div>
          <div className="text-xs text-gray-500 capitalize">{currentRoom.area}</div>
        </div>
      )}
    </div>
  );
};
