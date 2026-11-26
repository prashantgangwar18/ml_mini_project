import { useEffect, useMemo, useState } from 'react';
import {
  Bus,
  CloudRain,
  Gauge,
  LayoutDashboard,
  Map as MapIcon,
  Navigation,
  Search,
  Users,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { api, useLiveFleet } from './api/client';
import { AdminPanel } from './components/AdminPanel';
import { BusMap } from './components/BusMap';
import { DriverPanel } from './components/DriverPanel';
import { StopTimeline, formatClock, lateBadgeClasses } from './components/StopTimeline';
import type { Route } from './types';

type Tab = 'live' | 'driver' | 'admin';

export function App() {
  const [tab, setTab] = useState<Tab>('live');
  const [routes, setRoutes] = useState<Route[]>([]);
  const { buses, setBuses, simulator, setSimulator, connected } = useLiveFleet();
  const [selectedBusId, setSelectedBusId] = useState<number | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState<number | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [watchedStopId, setWatchedStopId] = useState<number | null>(null);

  useEffect(() => {
    api.getRoutes().then(setRoutes).catch(() => {});
  }, []);

  const filteredBuses = useMemo(() => {
    return buses.filter((b) => {
      if (selectedRouteId !== 'all' && b.route_id !== selectedRouteId) return false;
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        b.bus_number.toLowerCase().includes(q) ||
        b.route_name.toLowerCase().includes(q) ||
        b.driver_name.toLowerCase().includes(q) ||
        b.predictions.some((p) => p.stop_name.toLowerCase().includes(q))
      );
    });
  }, [buses, selectedRouteId, searchQuery]);

  const selectedBus =
    buses.find((b) => b.id === selectedBusId) ?? filteredBuses[0] ?? buses[0] ?? null;

  useEffect(() => {
    if (!selectedBusId && buses.length > 0) {
      setSelectedBusId(buses[0].id);
    }
  }, [buses, selectedBusId]);

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* Top Bar */}
      <header className="border-b border-slate-800 bg-slate-950/90 backdrop-blur sticky top-0 z-50">
        <div className="max-w-[1600px] mx-auto px-4 h-14 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-sky-500/15 border border-sky-500/40 flex items-center justify-center text-sky-400">
              <Bus className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-white leading-tight">
                CampusPulse Bus Tracker
              </h1>
              <p className="text-[11px] text-slate-400">
                Real-Time GPS · LightGBM TOA &amp; Late Prediction
              </p>
            </div>
          </div>

          <nav className="flex items-center gap-1 bg-slate-900 p-1 rounded-xl border border-slate-800">
            <button
              type="button"
              onClick={() => setTab('live')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer transition ${
                tab === 'live'
                  ? 'bg-sky-500 text-slate-950'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              <MapIcon className="w-3.5 h-3.5" />
              Live Tracking
            </button>
            <button
              type="button"
              onClick={() => setTab('driver')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer transition ${
                tab === 'driver'
                  ? 'bg-sky-500 text-slate-950'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              <Navigation className="w-3.5 h-3.5" />
              Driver GPS
            </button>
            <button
              type="button"
              onClick={() => setTab('admin')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer transition ${
                tab === 'admin'
                  ? 'bg-sky-500 text-slate-950'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              Admin &amp; ML
            </button>
          </nav>

          <div className="flex items-center gap-2 text-xs">
            {simulator && (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-slate-300">
                <CloudRain className="w-3.5 h-3.5 text-sky-400" />
                {simulator.weather} · {simulator.traffic_level} Traffic
              </span>
            )}
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border ${
                connected
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              }`}
            >
              {connected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
              {connected ? 'Live' : 'Reconnecting'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      {tab === 'live' && (
        <main className="flex-1 max-w-[1600px] w-full mx-auto p-4 grid grid-cols-1 lg:grid-cols-12 gap-4 h-[calc(100vh-3.5rem)]">
          {/* Left Fleet List */}
          <section className="lg:col-span-3 flex flex-col gap-3 min-h-0">
            <div className="rounded-2xl bg-slate-900 border border-slate-800 p-3 space-y-2.5">
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search bus, route, or stop..."
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-sky-500"
                />
              </div>
              <div className="flex gap-1.5 overflow-x-auto pb-1">
                <button
                  type="button"
                  onClick={() => setSelectedRouteId('all')}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-medium shrink-0 cursor-pointer ${
                    selectedRouteId === 'all'
                      ? 'bg-sky-500 text-slate-950'
                      : 'bg-slate-800 text-slate-300'
                  }`}
                >
                  All Routes
                </button>
                {routes.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setSelectedRouteId(r.id)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-medium shrink-0 cursor-pointer ${
                      selectedRouteId === r.id
                        ? 'bg-sky-500 text-slate-950'
                        : 'bg-slate-800 text-slate-300'
                    }`}
                  >
                    {r.code}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {filteredBuses.map((bus) => {
                const isSelected = selectedBus?.id === bus.id;
                const status = bus.campus_prediction?.late_status ?? 'On Time';

                return (
                  <button
                    key={bus.id}
                    type="button"
                    onClick={() => setSelectedBusId(bus.id)}
                    className={`w-full text-left rounded-2xl border p-3.5 transition cursor-pointer ${
                      isSelected
                        ? 'bg-sky-500/10 border-sky-500/60'
                        : 'bg-slate-900/90 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className="w-2.5 h-2.5 rounded-full shrink-0"
                          style={{ backgroundColor: bus.route_color }}
                        />
                        <span className="font-bold text-sm text-white">{bus.bus_number}</span>
                        <span className="text-[11px] text-slate-400">{bus.route_code}</span>
                      </div>
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${lateBadgeClasses(
                          status
                        )}`}
                      >
                        {status}
                      </span>
                    </div>

                    <div className="text-xs text-slate-300 mt-1 truncate">{bus.route_name}</div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2.5 pt-2 border-t border-slate-800/80">
                      <span className="inline-flex items-center gap-1">
                        <Gauge className="w-3 h-3" />
                        {bus.current_speed_kmh} km/h
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Users className="w-3 h-3" />
                        {bus.occupancy_pct}% full
                      </span>
                      {bus.campus_prediction && (
                        <span className="text-slate-200 font-medium">
                          Campus {formatClock(bus.campus_prediction.predicted_toa)}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Center Interactive Map */}
          <section className="lg:col-span-5 min-h-[380px] lg:min-h-0">
            <BusMap
              routes={routes}
              buses={filteredBuses}
              selectedBusId={selectedBus?.id ?? null}
              onSelectBus={(id) => setSelectedBusId(id)}
            />
          </section>

          {/* Right Stop Timeline & ML Predictions */}
          <section className="lg:col-span-4 overflow-y-auto pr-1 min-h-0">
            {selectedBus ? (
              <div className="space-y-3">
                <div className="rounded-2xl bg-slate-900 border border-slate-800 p-3.5 flex items-center justify-between">
                  <div>
                    <div className="text-sm font-bold text-white">
                      {selectedBus.bus_number} · {selectedBus.route_name}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      Driver: {selectedBus.driver_name} · {selectedBus.current_speed_kmh} km/h
                    </div>
                  </div>
                  <div className="text-right text-[11px] text-slate-400">
                    <div>Occupancy</div>
                    <div className="text-sm font-bold text-slate-100">
                      {selectedBus.occupancy_pct}%
                    </div>
                  </div>
                </div>
                <StopTimeline
                  bus={selectedBus}
                  watchedStopId={watchedStopId}
                  onWatchStop={setWatchedStopId}
                />
              </div>
            ) : (
              <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 text-sm text-slate-400">
                Select a bus to view stop-by-stop ML predictions.
              </div>
            )}
          </section>
        </main>
      )}

      {tab === 'driver' && (
        <main className="flex-1 overflow-y-auto">
          <DriverPanel
            buses={buses}
            routes={routes}
            onBusUpdated={(updated) =>
              setBuses((prev) => prev.map((b) => (b.id === updated.id ? updated : b)))
            }
          />
        </main>
      )}

      {tab === 'admin' && (
        <main className="flex-1 overflow-y-auto">
          <AdminPanel
            buses={buses}
            simulator={simulator}
            onSimulatorChange={(sim) => setSimulator(sim)}
          />
        </main>
      )}
    </div>
  );
}

export default App;
