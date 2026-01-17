// React app entry point
import { useGameStore } from './store/gameStore';
import { MudOutput } from './components/MudOutput';
import { CommandInput } from './components/CommandInput';
import { ActionButtons } from './components/ActionButtons';
import { PlayerStatus } from './components/PlayerStatus';
import { RoomVisualization } from './components/RoomVisualization';
import { MapView } from './components/MapView';
import { ConnectionPanel } from './components/ConnectionPanel';
import { Swords, Terminal } from 'lucide-react';

function App() {
  const connected = useGameStore((state) => state.connected);
  
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-orange-600 rounded-lg flex items-center justify-center">
              <Terminal size={24} />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">LLMUD</h1>
              <p className="text-sm text-gray-400">AI-Powered MUD Client</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            {connected && (
              <div className="flex items-center gap-2 text-green-400 text-sm">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                Connected
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Main Game View */}
          <div className="lg:col-span-2 space-y-4">
            {/* Room Visualization */}
            <RoomVisualization />
            
            {/* MUD Output */}
            <div className="card h-96 flex flex-col">
              <div className="flex items-center gap-2 mb-3 text-gray-400">
                <Terminal size={16} />
                <span className="text-sm font-medium">Game Output</span>
              </div>
              <div className="flex-1 overflow-hidden rounded bg-gray-900">
                <MudOutput />
              </div>
            </div>
            
            {/* Command Input */}
            <div className="card">
              <CommandInput />
            </div>
            
            {/* Action Buttons */}
            <div className="card">
              <div className="flex items-center gap-2 mb-3 text-gray-400">
                <Swords size={16} />
                <span className="text-sm font-medium">Actions</span>
              </div>
              <ActionButtons />
            </div>
          </div>

          {/* Right Column - Status and Controls */}
          <div className="space-y-4">
            {/* Connection Panel */}
            <ConnectionPanel />
            
            {/* Player Status */}
            <PlayerStatus />
            
            {/* Map View */}
            <MapView />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 border-t border-gray-700 px-6 py-4 mt-8">
        <div className="max-w-7xl mx-auto text-center text-sm text-gray-400">
          LLMUD - AI-Powered MUD Client for DuneMUD •{' '}
          <a 
            href="https://dunemud.net" 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-orange-400 hover:text-orange-300"
          >
            dunemud.net
          </a>
        </div>
      </footer>
    </div>
  );
}

export default App;
