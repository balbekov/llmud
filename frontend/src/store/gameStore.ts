import { create } from 'zustand';

export interface CharacterVitals {
  hp: number;
  maxhp: number;
  cp: number;
  maxcp: number;
  hp_percent: number;
  cp_percent: number;
}

export interface CharacterStats {
  str: number;
  con: number;
  int: number;
  wis: number;
  dex: number;
  qui: number;
}

export interface Character {
  name: string;
  guild: string;
  level: number;
  money: number;
  bank: number;
  wimpy: number;
  vitals: CharacterVitals;
  stats: CharacterStats;
}

export interface Room {
  name: string;
  area: string;
  environment: string;
  exits: string[];
  description?: string;
}

export interface ActionButton {
  label: string;
  command: string;
  type: 'navigation' | 'combat' | 'interaction' | 'info';
  style?: string;
}

export interface MapRoom {
  id: string;
  name: string;
  area: string;
  environment: string;
  exits: Record<string, string>;
  tags: string[];
  visit_count: number;
  is_current: boolean;
  has_items: boolean;
  has_npcs: boolean;
  has_image: boolean;
  x: number;
  y: number;
  z: number;
}

export interface MapEdge {
  from: string;
  to: string;
  direction: string;
  bidirectional: boolean;
}

export interface MapData {
  rooms: MapRoom[];
  edges: MapEdge[];
  current_room_id: string | null;
  stats: {
    total_rooms: number;
    total_edges: number;
    areas: Record<string, number>;
  };
}

export interface GameMessage {
  id: string;
  text: string;
  timestamp: Date;
  type: 'text' | 'system' | 'chat' | 'combat';
}

export interface GameState {
  // Connection
  connected: boolean;
  sessionId: string | null;
  
  // Game state
  phase: string;
  autoPlay: boolean;
  paused: boolean;
  
  // Character
  character: Character | null;
  
  // Room
  currentRoom: Room | null;
  roomImage: string | null;
  loadingRoomImage: boolean;
  
  // Combat
  inCombat: boolean;
  
  // Messages
  messages: GameMessage[];
  
  // Map
  mapData: MapData | null;
  exploredRooms: MapRoom[];
  
  // Actions
  actionButtons: ActionButton[];
  
  // UI State
  showMap: boolean;
  showSettings: boolean;
  commandHistory: string[];
  historyIndex: number;
}

export interface GameActions {
  // Connection actions
  setConnected: (connected: boolean) => void;
  setSessionId: (sessionId: string | null) => void;
  
  // Game state actions
  setPhase: (phase: string) => void;
  setAutoPlay: (autoPlay: boolean) => void;
  setPaused: (paused: boolean) => void;
  
  // Character actions
  setCharacter: (character: Character | null) => void;
  updateVitals: (vitals: Partial<CharacterVitals>) => void;
  
  // Room actions
  setCurrentRoom: (room: Room | null) => void;
  setRoomImage: (url: string | null) => void;
  setLoadingRoomImage: (loading: boolean) => void;
  
  // Combat actions
  setInCombat: (inCombat: boolean) => void;
  
  // Message actions
  addMessage: (text: string, type?: GameMessage['type']) => void;
  clearMessages: () => void;
  
  // Map actions
  updateMapData: (data: MapData) => void;
  updateExploredRooms: (rooms: MapRoom[]) => void;
  
  // Button actions
  setActionButtons: (buttons: ActionButton[]) => void;
  
  // UI actions
  toggleMap: () => void;
  toggleSettings: () => void;
  addCommandToHistory: (command: string) => void;
  setHistoryIndex: (index: number) => void;
  
  // Reset
  reset: () => void;
}

const initialState: GameState = {
  connected: false,
  sessionId: null,
  phase: 'disconnected',
  autoPlay: false,
  paused: false,
  character: null,
  currentRoom: null,
  roomImage: null,
  loadingRoomImage: false,
  inCombat: false,
  messages: [],
  mapData: null,
  exploredRooms: [],
  actionButtons: [],
  showMap: false,
  showSettings: false,
  commandHistory: [],
  historyIndex: -1,
};

export const useGameStore = create<GameState & GameActions>((set) => ({
  ...initialState,
  
  setConnected: (connected) => set({ connected }),
  setSessionId: (sessionId) => set({ sessionId }),
  setPhase: (phase) => set({ phase }),
  setAutoPlay: (autoPlay) => set({ autoPlay }),
  setPaused: (paused) => set({ paused }),
  
  setCharacter: (character) => set({ character }),
  updateVitals: (vitals) => set((state) => ({
    character: state.character ? {
      ...state.character,
      vitals: { ...state.character.vitals, ...vitals },
    } : null,
  })),
  
  setCurrentRoom: (room) => set({ currentRoom: room }),
  setRoomImage: (url) => set({ roomImage: url }),
  setLoadingRoomImage: (loading) => set({ loadingRoomImage: loading }),
  
  setInCombat: (inCombat) => set({ inCombat }),
  
  addMessage: (text, type = 'text') => set((state) => ({
    messages: [
      ...state.messages.slice(-500), // Keep last 500 messages
      {
        id: `${Date.now()}-${Math.random()}`,
        text,
        timestamp: new Date(),
        type,
      },
    ],
  })),
  clearMessages: () => set({ messages: [] }),
  
  updateMapData: (data) => set({ mapData: data, exploredRooms: data.rooms }),
  updateExploredRooms: (rooms) => set({ exploredRooms: rooms }),
  
  setActionButtons: (buttons) => set({ actionButtons: buttons }),
  
  toggleMap: () => set((state) => ({ showMap: !state.showMap })),
  toggleSettings: () => set((state) => ({ showSettings: !state.showSettings })),
  
  addCommandToHistory: (command) => set((state) => ({
    commandHistory: [...state.commandHistory.slice(-100), command],
    historyIndex: -1,
  })),
  setHistoryIndex: (index) => set({ historyIndex: index }),
  
  reset: () => set(initialState),
}));
