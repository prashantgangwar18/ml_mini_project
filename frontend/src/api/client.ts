import { useEffect, useRef, useState } from 'react';
import type {
  AdminOverview,
  BusSummary,
  MLMetrics,
  Route,
  SimulatorStatus,
  TrafficType,
  WeatherType,
} from '../types';

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  getRoutes: () => requestJson<Route[]>('/api/routes'),
  getBuses: (routeId?: number) =>
    requestJson<BusSummary[]>(routeId ? `/api/buses?route_id=${routeId}` : '/api/buses'),
  sendTelemetry: (payload: {
    bus_id: number;
    lat: number;
    lon: number;
    speed_kmh: number;
    occupancy_pct?: number;
    weather?: WeatherType;
    traffic_level?: TrafficType;
  }) =>
    requestJson<BusSummary>('/api/telemetry', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getAdminOverview: () => requestJson<AdminOverview>('/api/admin/overview'),
  getMLMetrics: () => requestJson<MLMetrics>('/api/admin/metrics'),
  retrainModels: (regenerateData = false) =>
    requestJson<{ status: string; metrics: MLMetrics }>(
      `/api/admin/retrain?regenerate_data=${regenerateData}`,
      { method: 'POST' }
    ),
  updateSimulator: (payload: {
    running?: boolean;
    weather?: WeatherType;
    traffic_level?: TrafficType;
    speed_multiplier?: number;
    inject_delay_bus_id?: number;
    inject_delay_min?: number;
  }) =>
    requestJson<SimulatorStatus>('/api/admin/simulator', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

export function useLiveFleet() {
  const [buses, setBuses] = useState<BusSummary[]>([]);
  const [simulator, setSimulator] = useState<SimulatorStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let active = true;
    let reconnectTimer: number | undefined;

    api.getBuses().then((data) => {
      if (active) setBuses(data);
    }).catch(() => {});

    const connectWs = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/live`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (active) setConnected(true);
      };
      ws.onmessage = (evt) => {
        if (!active) return;
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === 'fleet_update') {
            setBuses(msg.buses || []);
            if (msg.simulator) setSimulator(msg.simulator);
          }
        } catch {
          // ignore malformed messages
        }
      };
      ws.onclose = () => {
        if (!active) return;
        setConnected(false);
        reconnectTimer = window.setTimeout(connectWs, 2500);
      };
      ws.onerror = () => {
        ws.close();
      };
    };

    connectWs();

    return () => {
      active = false;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, []);

  return { buses, setBuses, simulator, setSimulator, connected };
}
