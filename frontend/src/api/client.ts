import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface ConnectParams {
  host?: string;
  port?: number;
  username?: string;
  password?: string;
  llm_provider?: string;
  auto_play?: boolean;
}

export interface SessionState {
  connected: boolean;
  phase: string;
  auto_mode: boolean;
  paused: boolean;
  character: any;
  room: any;
  combat: any;
  navigation: any;
  world_map_size: number;
}

export interface ActionButton {
  label: string;
  command: string;
  type: string;
}

// API functions
export async function getConfig() {
  const response = await api.get('/api/config');
  return response.data;
}

export async function createSession(params: ConnectParams = {}) {
  const response = await api.post('/api/sessions', params);
  return response.data;
}

export async function getSession(sessionId: string): Promise<SessionState> {
  const response = await api.get(`/api/sessions/${sessionId}`);
  return response.data;
}

export async function sendCommand(sessionId: string, command: string) {
  const response = await api.post(`/api/sessions/${sessionId}/command`, { command });
  return response.data;
}

export async function requestAIAction(sessionId: string, task: string = '') {
  const response = await api.post(`/api/sessions/${sessionId}/ai-action`, { task });
  return response.data;
}

export async function setAutoPlay(sessionId: string, enabled: boolean) {
  const response = await api.post(`/api/sessions/${sessionId}/auto-play?enabled=${enabled}`);
  return response.data;
}

export async function getActionButtons(sessionId: string): Promise<{ buttons: ActionButton[] }> {
  const response = await api.get(`/api/sessions/${sessionId}/buttons`);
  return response.data;
}

export interface MapRoomData {
  id: string;
  name: string;
  area: string;
  environment: string;
  x: number;
  y: number;
  z: number;
  exits: Record<string, string>;
  tags: string[];
  visit_count: number;
  is_current: boolean;
  has_items: boolean;
  has_npcs: boolean;
  has_image: boolean;
}

export interface MapEdgeData {
  from: string;
  to: string;
  direction: string;
  bidirectional: boolean;
}

export interface MapDataResponse {
  rooms: MapRoomData[];
  edges: MapEdgeData[];
  current_room_id: string | null;
  stats: {
    total_rooms: number;
    total_edges: number;
    areas: Record<string, number>;
  };
}

export async function getMap(sessionId: string): Promise<MapDataResponse> {
  const response = await api.get(`/api/sessions/${sessionId}/map`);
  return response.data;
}

export async function deleteSession(sessionId: string) {
  const response = await api.delete(`/api/sessions/${sessionId}`);
  return response.data;
}

export async function generateRoomImage(params: {
  room_name: string;
  description: string;
  area?: string;
  environment?: string;
}) {
  const response = await api.post('/api/generate-image', params);
  return response.data;
}

// WebSocket connection
export function createWebSocket(sessionId: string): WebSocket {
  const wsUrl = API_URL.replace('http', 'ws');
  return new WebSocket(`${wsUrl}/ws/${sessionId}`);
}
