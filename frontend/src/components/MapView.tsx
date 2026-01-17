import { useCallback, useMemo, useEffect, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  Handle,
  Panel,
} from '@xyflow/react';
import type { Node, Edge, NodeProps } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useGameStore, type MapRoom, type MapEdge as MapEdgeType } from '../store/gameStore';
import { Map, Maximize2, Home, Users, Package, Image } from 'lucide-react';

// Direction to position mapping for handles
const directionToSourcePosition: Record<string, Position> = {
  n: Position.Top,
  s: Position.Bottom,
  e: Position.Right,
  w: Position.Left,
  ne: Position.Right,
  nw: Position.Left,
  se: Position.Right,
  sw: Position.Left,
  u: Position.Top,
  d: Position.Bottom,
  enter: Position.Bottom,
  out: Position.Top,
};

const directionToTargetPosition: Record<string, Position> = {
  n: Position.Bottom,
  s: Position.Top,
  e: Position.Left,
  w: Position.Right,
  ne: Position.Left,
  nw: Position.Right,
  se: Position.Left,
  sw: Position.Right,
  u: Position.Bottom,
  d: Position.Top,
  enter: Position.Top,
  out: Position.Bottom,
};

// Get environment color
function getEnvironmentColor(environment: string, isCurrent: boolean): string {
  if (isCurrent) return '#f97316'; // Orange for current room
  
  const envColors: Record<string, string> = {
    indoor: '#6366f1', // Indigo
    outdoor: '#22c55e', // Green
    desert: '#eab308', // Yellow
    city: '#8b5cf6', // Purple
    water: '#06b6d4', // Cyan
    underground: '#78716c', // Stone
    forest: '#15803d', // Dark green
    mountain: '#71717a', // Gray
  };
  
  return envColors[environment?.toLowerCase()] || '#4b5563';
}

// Custom Room Node Component
function RoomNodeComponent({ data, selected }: NodeProps) {
  const room = data.room as MapRoom;
  const isCurrent = room.is_current;
  const bgColor = getEnvironmentColor(room.environment, isCurrent);
  
  return (
    <div
      className={`
        relative px-3 py-2 rounded-lg border-2 min-w-[120px] max-w-[180px]
        transition-all duration-200 shadow-lg
        ${isCurrent ? 'border-yellow-400 shadow-yellow-500/30' : 'border-gray-600'}
        ${selected ? 'ring-2 ring-blue-400' : ''}
      `}
      style={{ backgroundColor: bgColor }}
    >
      {/* Handles for all directions */}
      <Handle type="target" position={Position.Top} id="top" className="!bg-gray-400 !w-2 !h-2" />
      <Handle type="target" position={Position.Bottom} id="bottom" className="!bg-gray-400 !w-2 !h-2" />
      <Handle type="target" position={Position.Left} id="left" className="!bg-gray-400 !w-2 !h-2" />
      <Handle type="target" position={Position.Right} id="right" className="!bg-gray-400 !w-2 !h-2" />
      <Handle type="source" position={Position.Top} id="top-source" className="!bg-gray-400 !w-2 !h-2" />
      <Handle type="source" position={Position.Bottom} id="bottom-source" className="!bg-gray-400 !w-2 !h-2" />
      <Handle type="source" position={Position.Left} id="left-source" className="!bg-gray-400 !w-2 !h-2" />
      <Handle type="source" position={Position.Right} id="right-source" className="!bg-gray-400 !w-2 !h-2" />
      
      {/* Room name */}
      <div className="text-white text-sm font-semibold truncate text-center">
        {room.name}
      </div>
      
      {/* Area label */}
      {room.area && (
        <div className="text-white/70 text-xs truncate text-center mt-0.5">
          {room.area}
        </div>
      )}
      
      {/* Indicators row */}
      <div className="flex items-center justify-center gap-1.5 mt-1.5">
        {isCurrent && (
          <div className="flex items-center gap-0.5 text-yellow-300" title="Current location">
            <Home size={12} />
          </div>
        )}
        {room.has_npcs && (
          <div className="flex items-center gap-0.5 text-red-300" title="NPCs present">
            <Users size={12} />
          </div>
        )}
        {room.has_items && (
          <div className="flex items-center gap-0.5 text-blue-300" title="Items present">
            <Package size={12} />
          </div>
        )}
        {room.has_image && (
          <div className="flex items-center gap-0.5 text-purple-300" title="Has image">
            <Image size={12} />
          </div>
        )}
        {room.visit_count > 1 && (
          <span className="text-white/60 text-xs" title={`Visited ${room.visit_count} times`}>
            ×{room.visit_count}
          </span>
        )}
      </div>
      
      {/* Tags */}
      {room.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5 justify-center">
          {room.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="px-1.5 py-0.5 bg-black/30 rounded text-[10px] text-white/80"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

const nodeTypes = {
  roomNode: RoomNodeComponent,
};

// Convert map data to ReactFlow nodes and edges
function convertToFlowElements(
  rooms: MapRoom[],
  edges: MapEdgeType[]
): { nodes: Node[]; edges: Edge[] } {
  // Scale factor for positioning
  const SCALE = 200;
  const OFFSET = 500;
  
  // Convert rooms to nodes
  const nodes: Node[] = rooms.map((room) => ({
    id: room.id,
    type: 'roomNode',
    position: {
      x: (room.x ?? 0) * SCALE + OFFSET,
      y: (room.y ?? 0) * SCALE + OFFSET,
    },
    data: { room },
    draggable: true,
  }));
  
  // Convert edges to ReactFlow edges
  const flowEdges: Edge[] = [];
  const seenEdges = new Set<string>();
  
  edges.forEach((edge) => {
    const edgeKey = `${edge.from}-${edge.to}`;
    const reverseKey = `${edge.to}-${edge.from}`;
    
    // Skip if we've already added this edge or its reverse (for bidirectional)
    if (seenEdges.has(edgeKey) || (edge.bidirectional && seenEdges.has(reverseKey))) {
      return;
    }
    
    seenEdges.add(edgeKey);
    
    const sourcePosition = directionToSourcePosition[edge.direction] || Position.Bottom;
    const targetPosition = directionToTargetPosition[edge.direction] || Position.Top;
    
    flowEdges.push({
      id: `${edge.from}-${edge.direction}-${edge.to}`,
      source: edge.from,
      target: edge.to,
      sourceHandle: `${sourcePosition.toLowerCase()}-source`,
      targetHandle: targetPosition.toLowerCase(),
      type: 'smoothstep',
      animated: false,
      style: { stroke: '#6b7280', strokeWidth: 2 },
      markerEnd: edge.bidirectional ? undefined : {
        type: MarkerType.ArrowClosed,
        color: '#6b7280',
      },
      label: edge.direction,
      labelStyle: { fill: '#9ca3af', fontSize: 10 },
      labelBgStyle: { fill: '#1f2937', fillOpacity: 0.8 },
      labelBgPadding: [4, 2] as [number, number],
      labelBgBorderRadius: 4,
    });
  });
  
  return { nodes, edges: flowEdges };
}

export const MapView: React.FC = () => {
  const mapData = useGameStore((state) => state.mapData);
  const exploredRooms = useGameStore((state) => state.exploredRooms);
  const currentRoom = useGameStore((state) => state.currentRoom);
  const showMap = useGameStore((state) => state.showMap);
  const toggleMap = useGameStore((state) => state.toggleMap);
  
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  
  // Convert map data to ReactFlow elements
  useEffect(() => {
    if (mapData && mapData.rooms.length > 0) {
      const { nodes: flowNodes, edges: flowEdges } = convertToFlowElements(
        mapData.rooms,
        mapData.edges
      );
      setNodes(flowNodes);
      setEdges(flowEdges);
    }
  }, [mapData, setNodes, setEdges]);
  
  // Fit view when current room changes
  const onInit = useCallback((reactFlowInstance: { fitView: (options?: { padding?: number }) => void }) => {
    setTimeout(() => {
      reactFlowInstance.fitView({ padding: 0.2 });
    }, 100);
  }, []);
  
  // Group rooms by area for legend
  const roomsByArea = useMemo(() => {
    const groups: Record<string, number> = {};
    exploredRooms.forEach((room) => {
      const area = room.area || 'Unknown';
      groups[area] = (groups[area] || 0) + 1;
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
  
  const mapContainerClass = isFullscreen
    ? 'fixed inset-0 z-50 bg-gray-900'
    : 'card';
  
  const mapHeight = isFullscreen ? 'h-full' : 'h-96';
  
  return (
    <div className={mapContainerClass}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Map size={20} className="text-orange-500" />
          <h3 className="font-semibold text-white">World Map</h3>
          <span className="text-sm text-gray-400">
            ({mapData?.stats?.total_rooms || exploredRooms.length} rooms, {mapData?.stats?.total_edges || 0} connections)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            <Maximize2 size={16} />
          </button>
          <button
            onClick={toggleMap}
            className="text-gray-400 hover:text-white text-sm px-2 py-1 hover:bg-gray-700 rounded"
          >
            Hide
          </button>
        </div>
      </div>
      
      {/* Area Legend */}
      <div className="flex flex-wrap gap-2 p-2 border-b border-gray-700 bg-gray-800/50">
        {Object.entries(roomsByArea).map(([area, count]) => (
          <span
            key={area}
            className="px-2 py-1 bg-gray-700 rounded text-xs text-gray-300"
          >
            {area}: {count}
          </span>
        ))}
      </div>
      
      {/* ReactFlow Map */}
      <div className={`${mapHeight} bg-gray-900`}>
        {nodes.length > 0 ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onInit={onInit}
            nodeTypes={nodeTypes}
            fitView
            minZoom={0.1}
            maxZoom={2}
            defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#374151" gap={20} size={1} />
            <Controls 
              className="!bg-gray-800 !border-gray-700 !shadow-lg"
              showInteractive={false}
            />
            <MiniMap
              className="!bg-gray-800 !border-gray-700"
              nodeColor={(node) => {
                const room = node.data?.room as MapRoom;
                return room?.is_current ? '#f97316' : '#4b5563';
              }}
              maskColor="rgba(0, 0, 0, 0.7)"
            />
            
            {/* Current Location Panel */}
            {currentRoom && (
              <Panel position="bottom-left" className="!bg-gray-800 !border-gray-700 rounded-lg p-2 shadow-lg">
                <div className="text-xs text-gray-400">Current Location:</div>
                <div className="text-sm text-orange-400 font-medium">{currentRoom.name}</div>
                {currentRoom.area && (
                  <div className="text-xs text-gray-500">{currentRoom.area}</div>
                )}
              </Panel>
            )}
            
            {/* Legend Panel */}
            <Panel position="top-right" className="!bg-gray-800 !border-gray-700 rounded-lg p-2 shadow-lg">
              <div className="text-xs text-gray-400 mb-2">Legend</div>
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-xs">
                  <div className="w-3 h-3 rounded bg-orange-500"></div>
                  <span className="text-gray-300">Current</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <div className="w-3 h-3 rounded bg-indigo-500"></div>
                  <span className="text-gray-300">Indoor</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <div className="w-3 h-3 rounded bg-green-500"></div>
                  <span className="text-gray-300">Outdoor</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <div className="w-3 h-3 rounded bg-yellow-500"></div>
                  <span className="text-gray-300">Desert</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <Users size={12} className="text-red-300" />
                  <span className="text-gray-300">NPCs</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <Package size={12} className="text-blue-300" />
                  <span className="text-gray-300">Items</span>
                </div>
              </div>
            </Panel>
          </ReactFlow>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <Map size={48} className="mx-auto mb-3 opacity-50" />
              <p>No rooms explored yet</p>
              <p className="text-sm text-gray-600">Start exploring to build the map!</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
