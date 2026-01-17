import { useMemo, useState } from 'react';
import { useGameStore, type MapRoom } from '../store/gameStore';
import { Map, ZoomIn, ZoomOut, Compass } from 'lucide-react';

// Simple force-directed layout calculation
function calculateLayout(rooms: MapRoom[]): MapRoom[] {
  if (rooms.length === 0) return [];
  
  // Initialize positions
  const positioned = rooms.map((room, index) => ({
    ...room,
    x: Math.cos(index * 2 * Math.PI / rooms.length) * 200 + 300,
    y: Math.sin(index * 2 * Math.PI / rooms.length) * 200 + 200,
  }));
  
  // Simple physics simulation
  const iterations = 50;
  for (let i = 0; i < iterations; i++) {
    positioned.forEach((room1, idx1) => {
      let fx = 0, fy = 0;
      
      positioned.forEach((room2, idx2) => {
        if (idx1 === idx2) return;
        
        const dx = room1.x! - room2.x!;
        const dy = room1.y! - room2.y!;
        const dist = Math.sqrt(dx * dx + dy * dy) + 1;
        
        // Repulsion
        const repulsion = 5000 / (dist * dist);
        fx += (dx / dist) * repulsion;
        fy += (dy / dist) * repulsion;
      });
      
      // Apply forces with damping
      room1.x! += fx * 0.1;
      room1.y! += fy * 0.1;
      
      // Keep in bounds
      room1.x = Math.max(50, Math.min(550, room1.x!));
      room1.y = Math.max(50, Math.min(350, room1.y!));
    });
  }
  
  return positioned;
}

interface RoomNodeProps {
  room: MapRoom;
  isCurrentRoom: boolean;
  onClick: (room: MapRoom) => void;
}

const RoomNode: React.FC<RoomNodeProps> = ({ room, isCurrentRoom, onClick }) => {
  const x = room.x || 0;
  const y = room.y || 0;
  
  return (
    <g 
      transform={`translate(${x}, ${y})`}
      onClick={() => onClick(room)}
      className="cursor-pointer"
    >
      <circle
        r={isCurrentRoom ? 12 : 8}
        fill={isCurrentRoom ? '#f97316' : '#4b5563'}
        stroke={isCurrentRoom ? '#fbbf24' : '#6b7280'}
        strokeWidth={2}
        className="transition-all duration-200 hover:fill-blue-500"
      />
      <text
        y={-16}
        textAnchor="middle"
        className="fill-gray-300 text-xs font-medium"
        style={{ fontSize: '10px' }}
      >
        {room.name.length > 15 ? room.name.slice(0, 15) + '...' : room.name}
      </text>
      {room.visits > 1 && (
        <text
          y={4}
          textAnchor="middle"
          className="fill-white text-xs"
          style={{ fontSize: '9px' }}
        >
          {room.visits}
        </text>
      )}
    </g>
  );
};

export const MapView: React.FC = () => {
  const exploredRooms = useGameStore((state) => state.exploredRooms);
  const currentRoom = useGameStore((state) => state.currentRoom);
  const showMap = useGameStore((state) => state.showMap);
  const toggleMap = useGameStore((state) => state.toggleMap);
  
  const [zoom, setZoom] = useState(1);
  
  const layoutRooms = useMemo(() => {
    return calculateLayout(exploredRooms);
  }, [exploredRooms]);
  
  // Group rooms by area
  const roomsByArea = useMemo(() => {
    const groups: Record<string, MapRoom[]> = {};
    exploredRooms.forEach(room => {
      const area = room.area || 'unknown';
      if (!groups[area]) groups[area] = [];
      groups[area].push(room);
    });
    return groups;
  }, [exploredRooms]);
  
  if (!showMap) {
    return (
      <button
        onClick={toggleMap}
        className="btn btn-secondary flex items-center gap-2"
      >
        <Map size={16} />
        Show Map ({exploredRooms.length} rooms)
      </button>
    );
  }
  
  const handleRoomClick = (room: MapRoom) => {
    console.log('Room clicked:', room);
    // Could navigate or show room details
  };
  
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Map size={20} className="text-orange-500" />
          <h3 className="font-semibold text-white">Explored Map</h3>
          <span className="text-sm text-gray-400">
            ({exploredRooms.length} rooms)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoom(z => Math.max(0.5, z - 0.25))}
            className="p-1 text-gray-400 hover:text-white"
          >
            <ZoomOut size={16} />
          </button>
          <span className="text-sm text-gray-400">{Math.round(zoom * 100)}%</span>
          <button
            onClick={() => setZoom(z => Math.min(2, z + 0.25))}
            className="p-1 text-gray-400 hover:text-white"
          >
            <ZoomIn size={16} />
          </button>
          <button
            onClick={toggleMap}
            className="text-gray-400 hover:text-white text-sm"
          >
            Hide
          </button>
        </div>
      </div>
      
      {/* Area Legend */}
      <div className="flex flex-wrap gap-2 mb-3">
        {Object.entries(roomsByArea).map(([area, rooms]) => (
          <span
            key={area}
            className="px-2 py-1 bg-gray-700 rounded text-xs text-gray-300 capitalize"
          >
            {area}: {rooms.length}
          </span>
        ))}
      </div>
      
      {/* Map SVG */}
      <div className="bg-gray-900 rounded-lg overflow-hidden">
        <svg
          viewBox={`0 0 ${600 / zoom} ${400 / zoom}`}
          className="w-full h-64"
          style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}
        >
          {/* Compass */}
          <g transform="translate(30, 30)">
            <Compass size={20} className="text-gray-600" />
            <text x={0} y={-12} textAnchor="middle" className="fill-gray-500 text-xs">N</text>
          </g>
          
          {/* Room nodes */}
          {layoutRooms.map((room) => (
            <RoomNode
              key={room.id}
              room={room}
              isCurrentRoom={currentRoom?.name === room.name}
              onClick={handleRoomClick}
            />
          ))}
        </svg>
      </div>
      
      {/* Current Location */}
      {currentRoom && (
        <div className="mt-3 text-sm">
          <span className="text-gray-400">Current:</span>{' '}
          <span className="text-orange-400 font-medium">{currentRoom.name}</span>
        </div>
      )}
    </div>
  );
};
