import { useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { generateRoomImage } from '../api/client';
import { Loader2, Image as ImageIcon, RefreshCw } from 'lucide-react';

export const RoomVisualization: React.FC = () => {
  const currentRoom = useGameStore((state) => state.currentRoom);
  const roomImage = useGameStore((state) => state.roomImage);
  const loadingRoomImage = useGameStore((state) => state.loadingRoomImage);
  const setRoomImage = useGameStore((state) => state.setRoomImage);
  const setLoadingRoomImage = useGameStore((state) => state.setLoadingRoomImage);
  
  const [error, setError] = useState<string | null>(null);
  
  const generateImage = async () => {
    if (!currentRoom) return;
    
    setLoadingRoomImage(true);
    setError(null);
    
    try {
      const result = await generateRoomImage({
        room_name: currentRoom.name,
        description: currentRoom.description || currentRoom.name,
        area: currentRoom.area,
        environment: currentRoom.environment,
      });
      
      setRoomImage(result.image_url);
    } catch (err) {
      console.error('Failed to generate image:', err);
      setError('Failed to generate image');
    } finally {
      setLoadingRoomImage(false);
    }
  };
  
  // Auto-generate image when room changes (disabled by default to save API calls)
  // useEffect(() => {
  //   if (currentRoom && currentRoom.name !== lastRoomName) {
  //     generateImage();
  //   }
  // }, [currentRoom?.name]);
  
  if (!currentRoom) {
    return (
      <div className="card h-64 flex items-center justify-center text-gray-400">
        <div className="text-center">
          <ImageIcon size={48} className="mx-auto mb-2 opacity-50" />
          <p>No room data</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="card">
      {/* Room Header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-lg font-semibold text-white">{currentRoom.name}</h3>
          <p className="text-sm text-gray-400 capitalize">
            {currentRoom.area} • {currentRoom.environment}
          </p>
        </div>
        <button
          onClick={generateImage}
          disabled={loadingRoomImage}
          className="btn btn-secondary text-sm flex items-center gap-1"
        >
          {loadingRoomImage ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <RefreshCw size={16} />
          )}
          Generate
        </button>
      </div>
      
      {/* Image Display */}
      <div className="relative aspect-video bg-gray-800 rounded-lg overflow-hidden">
        {loadingRoomImage ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-gray-400">
              <Loader2 size={48} className="mx-auto mb-2 animate-spin" />
              <p>Generating visualization...</p>
            </div>
          </div>
        ) : roomImage ? (
          <img
            src={roomImage}
            alt={currentRoom.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-gray-500">
            <div className="text-center">
              <ImageIcon size={64} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">Click "Generate" to visualize this room</p>
            </div>
          </div>
        )}
        
        {error && (
          <div className="absolute bottom-0 left-0 right-0 bg-red-900/80 text-white text-sm p-2 text-center">
            {error}
          </div>
        )}
      </div>
      
      {/* Exits */}
      <div className="mt-3">
        <div className="text-sm text-gray-400 mb-1">Exits</div>
        <div className="flex flex-wrap gap-2">
          {currentRoom.exits.map((exit) => (
            <span
              key={exit}
              className="px-2 py-1 bg-gray-700 rounded text-sm text-white"
            >
              {exit.toUpperCase()}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
