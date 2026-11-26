import { useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  Pause,
  Play,
  RefreshCw,
  Zap,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api/client';
import type {
  AdminOverview,
  BusSummary,
  MLMetrics,
  SimulatorStatus,
  TrafficType,
  WeatherType,
} from '../types';

interface AdminPanelProps {
  buses: BusSummary[];
  simulator: SimulatorStatus | null;
  onSimulatorChange: (sim: SimulatorStatus) => void;
}

export function AdminPanel({ buses, simulator, onSimulatorChange }: AdminPanelProps) {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [metrics, setMetrics] = useState<MLMetrics | null>(null);
  const [retraining, setRetraining] = useState(false);
  const [delayBusId, setDelayBusId] = useState<number>(buses[0]?.id ?? 1);
  const [statusMsg, setStatusMsg] = useState('');

  async function loadData() {
    try {
      const [ov, met] = await Promise.all([api.getAdminOverview(), api.getMLMetrics()]);
      setOverview(ov);
      setMetrics(met);
      onSimulatorChange(ov.simulator);
    } catch {
      // ignore transient error
    }
  }

  useEffect(() => {
    loadData();
    const id = window.setInterval(loadData, 5000);
    return () => window.clearInterval(id);
  }, []);

  async function handleSimUpdate(patch: Parameters<typeof api.updateSimulator>[0]) {
    const updated = await api.updateSimulator(patch);
    onSimulatorChange(updated);
    await loadData();
  }

  async function handleRetrain() {
    setRetraining(true);
    setStatusMsg('Generating fresh trips and retraining LightGBM models...');
    try {
      const res = await api.retrainModels(true);
      setMetrics(res.metrics);
      setStatusMsg(
        `Retrained on ${res.metrics.dataset.total_samples.toLocaleString()} samples (TOA MAE: ${res.metrics.toa_models.lightgbm_toa.mae_min} min)`
      );
    } catch (err) {
      setStatusMsg(`Retrain failed: ${(err as Error).message}`);
    } finally {
      setRetraining(false);
    }
  }

  const sim = simulator ?? overview?.simulator;

  const comparisonData = metrics
    ? [
        {
          name: 'Heuristic',
          MAE: metrics.toa_models.heuristic_baseline.mae_min,
          RMSE: metrics.toa_models.heuristic_baseline.rmse_min,
        },
        {
          name: 'Ridge',
          MAE: metrics.toa_models.ridge_regression.mae_min,
          RMSE: metrics.toa_models.ridge_regression.rmse_min,
        },
        {
          name: 'LightGBM',
          MAE: metrics.toa_models.lightgbm_toa.mae_min,
          RMSE: metrics.toa_models.lightgbm_toa.rmse_min,
        },
      ]
    : [];

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4">
          <div className="text-xs text-slate-400">Active Buses</div>
          <div className="text-2xl font-bold text-white mt-1">
            {overview?.fleet.active_buses ?? buses.length}
          </div>
        </div>
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4">
          <div className="text-xs text-emerald-400">On Time</div>
          <div className="text-2xl font-bold text-emerald-300 mt-1">
            {overview?.fleet.on_time ?? 0}
          </div>
        </div>
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4">
          <div className="text-xs text-amber-400">Slightly Late</div>
          <div className="text-2xl font-bold text-amber-300 mt-1">
            {overview?.fleet.slightly_late ?? 0}
          </div>
        </div>
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4">
          <div className="text-xs text-rose-400">Late (&gt;7m)</div>
          <div className="text-2xl font-bold text-rose-300 mt-1">
            {overview?.fleet.late ?? 0}
          </div>
        </div>
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4">
          <div className="text-xs text-slate-400">ML TOA MAE</div>
          <div className="text-2xl font-bold text-sky-300 mt-1">
            {metrics ? `${metrics.toa_models.lightgbm_toa.mae_min}m` : '—'}
          </div>
        </div>
      </div>

      {/* Simulator & Scenario Controls */}
      <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-sky-400" />
            <h2 className="text-base font-bold text-white">Live Simulator & Scenario Controls</h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => handleSimUpdate({ running: !sim?.running })}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 border cursor-pointer ${
                sim?.running
                  ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                  : 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
              }`}
            >
              {sim?.running ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              {sim?.running ? 'Pause Simulation' : 'Resume Simulation'}
            </button>

            <button
              type="button"
              onClick={handleRetrain}
              disabled={retraining}
              className="px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 bg-sky-500 hover:bg-sky-400 text-slate-950 disabled:opacity-60 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${retraining ? 'animate-spin' : ''}`} />
              {retraining ? 'Retraining...' : 'Retrain ML Models'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Weather Condition</label>
            <select
              value={sim?.weather ?? 'Clear'}
              onChange={(e) => handleSimUpdate({ weather: e.target.value as WeatherType })}
              className="w-full rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-white"
            >
              <option value="Clear">Clear</option>
              <option value="Cloudy">Cloudy</option>
              <option value="Rain">Rain (Slowdown)</option>
              <option value="Fog">Fog (Slowdown)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">City Traffic Level</label>
            <select
              value={sim?.traffic_level ?? 'Moderate'}
              onChange={(e) => handleSimUpdate({ traffic_level: e.target.value as TrafficType })}
              className="w-full rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-white"
            >
              <option value="Low">Low</option>
              <option value="Moderate">Moderate</option>
              <option value="Heavy">Heavy (Congested)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Simulation Speed</label>
            <select
              value={sim?.speed_multiplier ?? 1}
              onChange={(e) => handleSimUpdate({ speed_multiplier: Number(e.target.value) })}
              className="w-full rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-white"
            >
              <option value={0.5}>0.5x</option>
              <option value={1}>1.0x (Default)</option>
              <option value={2}>2.0x</option>
              <option value={4}>4.0x (Fast Demo)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Inject Traffic Incident</label>
            <div className="flex gap-2">
              <select
                value={delayBusId}
                onChange={(e) => setDelayBusId(Number(e.target.value))}
                className="flex-1 rounded-xl bg-slate-950 border border-slate-700 px-2.5 py-2 text-sm text-white"
              >
                {buses.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.bus_number}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() =>
                  handleSimUpdate({ inject_delay_bus_id: delayBusId, inject_delay_min: 6.5 })
                }
                className="px-3 py-2 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 text-xs font-semibold flex items-center gap-1 cursor-pointer"
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                +6.5m
              </button>
            </div>
          </div>
        </div>

        {statusMsg && (
          <div className="mt-3 text-xs text-sky-300 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2">
            {statusMsg}
          </div>
        )}
      </div>

      {/* Analytics Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            Predicted Campus Delay by Route (min)
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={overview?.route_delays ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="route_code" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    color: '#f8fafc',
                  }}
                />
                <Bar dataKey="avg_delay_min" name="Avg Delay (min)" radius={[6, 6, 0, 0]}>
                  {(overview?.route_delays ?? []).map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
            <BrainCircuit className="w-4 h-4 text-sky-400" />
            TOA Model Error Comparison (Minutes — Lower is Better)
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={comparisonData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    color: '#f8fafc',
                  }}
                />
                <Bar dataKey="MAE" fill="#38bdf8" radius={[6, 6, 0, 0]} />
                <Bar dataKey="RMSE" fill="#818cf8" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ML Metrics & Feature Importance */}
      {metrics && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5 space-y-3">
            <h3 className="text-sm font-bold text-white">ML Evaluation Summary</h3>
            <div className="text-xs text-slate-400 space-y-2">
              <div className="flex justify-between">
                <span>Training / Test Samples</span>
                <span className="text-slate-200 font-medium">
                  {metrics.dataset.train_samples.toLocaleString()} /{' '}
                  {metrics.dataset.test_samples.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span>TOA LightGBM R²</span>
                <span className="text-emerald-300 font-semibold">
                  {metrics.toa_models.lightgbm_toa.r2}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Delay Regressor MAE</span>
                <span className="text-sky-300 font-semibold">
                  {metrics.delay_regression.mae_min} min
                </span>
              </div>
              <div className="flex justify-between">
                <span>Late Classifier Accuracy</span>
                <span className="text-emerald-300 font-semibold">
                  {(metrics.late_classification.accuracy * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span>Late Classifier Macro-F1</span>
                <span className="text-emerald-300 font-semibold">
                  {metrics.late_classification.macro_f1}
                </span>
              </div>
            </div>
          </div>

          <div className="lg:col-span-2 rounded-2xl bg-slate-900 border border-slate-800 p-5">
            <h3 className="text-sm font-bold text-white mb-3">
              Top Feature Importances (LightGBM TOA)
            </h3>
            <div className="space-y-2">
              {metrics.feature_importance.slice(0, 7).map((item) => (
                <div key={item.feature} className="flex items-center gap-3 text-xs">
                  <div className="w-52 text-slate-300 truncate font-mono">{item.feature}</div>
                  <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-sky-400 rounded-full"
                      style={{ width: `${Math.min(100, item.importance * 3.5)}%` }}
                    />
                  </div>
                  <div className="w-12 text-right text-slate-400">{item.importance}%</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
