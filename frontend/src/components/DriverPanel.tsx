import { useEffect, useState } from 'react';
import { Navigation, Radio, Send } from 'lucide-react';
import { api } from '../api/client';
import type { BusSummary, Route, TrafficType, WeatherType } from '../types';

interface DriverPanelProps {
  buses: BusSummary[];
  routes: Route[];
  onBusUpdated: (updated: BusSummary) => void;
}

export function DriverPanel({ buses, routes, onBusUpdated }: DriverPanelProps) {
  const [busId, setBusId] = useState<number>(buses[0]?.id ?? 1);
  const selectedBus = buses.find((b) => b.id === busId) ?? buses[0];
  const selectedRoute = routes.find((r) => r.id === selectedBus?.route_id);

  const [lat, setLat] = useState<string>('12.9352');
  const [lon, setLon] = useState<string>('77.6245');
  const [speed, setSpeed] = useState<string>('26');
  const [occupancy, setOccupancy] = useState<string>('68');
  const [weather, setWeather] = useState<WeatherType>('Clear');
  const [traffic, setTraffic] = useState<TrafficType>('Moderate');
  const [liveGpsOn, setLiveGpsOn] = useState(false);
  const [message, setMessage] = useState<string>('');

  useEffect(() => {
    if (selectedBus) {
      setLat(selectedBus.current_lat.toFixed(5));
      setLon(selectedBus.current_lon.toFixed(5));
      setSpeed(String(selectedBus.current_speed_kmh));
      setOccupancy(String(selectedBus.occupancy_pct));
      setWeather(selectedBus.weather);
      setTraffic(selectedBus.traffic_level);
    }
  }, [busId]);

  useEffect(() => {
    if (!liveGpsOn || !navigator.geolocation || !selectedBus) return;

    const watchId = navigator.geolocation.watchPosition(
      async (pos) => {
        const kmh = pos.coords.speed ? Math.max(0, pos.coords.speed * 3.6) : Number(speed) || 24;
        setLat(pos.coords.latitude.toFixed(5));
        setLon(pos.coords.longitude.toFixed(5));
        setSpeed(kmh.toFixed(1));
        try {
          const updated = await api.sendTelemetry({
            bus_id: selectedBus.id,
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            speed_kmh: kmh,
            occupancy_pct: Number(occupancy),
            weather,
            traffic_level: traffic,
          });
          onBusUpdated(updated);
          setMessage(`Live GPS ping sent at ${new Date().toLocaleTimeString()}`);
        } catch (err) {
          setMessage(`GPS send failed: ${(err as Error).message}`);
        }
      },
      (err) => {
        setMessage(`Geolocation unavailable: ${err.message}`);
        setLiveGpsOn(false);
      },
      { enableHighAccuracy: true, maximumAge: 3000 }
    );

    return () => navigator.geolocation.clearWatch(watchId);
  }, [liveGpsOn, selectedBus?.id, weather, traffic, occupancy]);

  async function handleManualPing(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedBus) return;
    try {
      const updated = await api.sendTelemetry({
        bus_id: selectedBus.id,
        lat: Number(lat),
        lon: Number(lon),
        speed_kmh: Number(speed),
        occupancy_pct: Number(occupancy),
        weather,
        traffic_level: traffic,
      });
      onBusUpdated(updated);
      setMessage(
        `Ping applied to ${updated.bus_number} — Campus TOA ${
          updated.campus_prediction ? `${updated.campus_prediction.remaining_min}m (${updated.campus_prediction.late_status})` : 'N/A'
        }`
      );
    } catch (err) {
      setMessage(`Error: ${(err as Error).message}`);
    }
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Navigation className="w-5 h-5 text-sky-400" />
              Driver GPS & Telemetry Console
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Stream live device GPS or push manual coordinates to test ML TOA & delay updates immediately.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setLiveGpsOn((v) => !v)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-2 border transition cursor-pointer ${
              liveGpsOn
                ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300'
                : 'bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700'
            }`}
          >
            <Radio className="w-4 h-4" />
            {liveGpsOn ? 'Streaming Device GPS...' : 'Start Device GPS Stream'}
          </button>
        </div>

        <form onSubmit={handleManualPing} className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Select Bus</label>
            <select
              value={selectedBus?.id ?? ''}
              onChange={(e) => setBusId(Number(e.target.value))}
              className="w-full rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-white"
            >
              {buses.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.bus_number} — {b.route_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Latitude</label>
            <input
              type="number"
              step="0.00001"
              value={lat}
              onChange={(e) => setLat(e.target.value)}
              className="w-full rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-white"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Longitude</label>
            <input
              type="number"
              step="0.00001"
              value={lon}
              onChange={(e) => setLon(e.target.value)}
              className="w-full rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-white"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Speed (km/h)</label>
            <input
              type="number"
              step="0.5"
              min="0"
              max="120"
              value={speed}
              onChange={(e) => setSpeed(e.target.value)}
              className="w-full rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-white"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Occupancy (%)</label>
            <input
              type="number"
              min="0"
              max="100"
              value={occupancy}
              onChange={(e) => setOccupancy(e.target.value)}
              className="w-full rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-white"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Weather</label>
              <select
                value={weather}
                onChange={(e) => setWeather(e.target.value as WeatherType)}
                className="w-full rounded-xl bg-slate-950 border border-slate-700 px-2.5 py-2 text-sm text-white"
              >
                <option value="Clear">Clear</option>
                <option value="Cloudy">Cloudy</option>
                <option value="Rain">Rain</option>
                <option value="Fog">Fog</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Traffic</label>
              <select
                value={traffic}
                onChange={(e) => setTraffic(e.target.value as TrafficType)}
                className="w-full rounded-xl bg-slate-950 border border-slate-700 px-2.5 py-2 text-sm text-white"
              >
                <option value="Low">Low</option>
                <option value="Moderate">Moderate</option>
                <option value="Heavy">Heavy</option>
              </select>
            </div>
          </div>

          <div className="md:col-span-3 flex flex-wrap items-center justify-between gap-3 pt-2">
            <div className="flex flex-wrap gap-1.5">
              {selectedRoute?.stops.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => {
                    setLat(s.lat.toFixed(5));
                    setLon(s.lon.toFixed(5));
                  }}
                  className="text-xs px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-pointer"
                >
                  Snap: {s.name}
                </button>
              ))}
            </div>
            <button
              type="submit"
              className="px-5 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold text-sm flex items-center gap-2 cursor-pointer"
            >
              <Send className="w-4 h-4" />
              Send Telemetry Ping
            </button>
          </div>
        </form>

        {message && (
          <div className="mt-4 rounded-xl bg-slate-950 border border-slate-800 px-4 py-2.5 text-xs text-sky-300">
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
