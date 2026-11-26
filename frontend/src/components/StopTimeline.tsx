import { Bell, BellRing, CheckCircle2, Clock, GraduationCap, MapPin } from 'lucide-react';
import type { BusSummary, LateStatus, StopPrediction } from '../types';

interface StopTimelineProps {
  bus: BusSummary;
  watchedStopId: number | null;
  onWatchStop: (stopId: number | null) => void;
}

export function lateBadgeClasses(status: LateStatus): string {
  switch (status) {
    case 'On Time':
      return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
    case 'Slightly Late':
      return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
    case 'Late':
      return 'bg-rose-500/15 text-rose-300 border-rose-500/30';
  }
}

export function formatClock(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function formatDelay(delayMin: number): string {
  const rounded = Math.round(delayMin * 10) / 10;
  if (rounded <= 0.4 && rounded >= -0.4) return 'On schedule';
  return rounded > 0 ? `+${rounded} min late` : `${Math.abs(rounded)} min early`;
}

function ProbabilityBar({ probs }: { probs: Record<string, number> }) {
  const onTime = Math.round((probs['On Time'] ?? 0) * 100);
  const slight = Math.round((probs['Slightly Late'] ?? 0) * 100);
  const late = Math.round((probs['Late'] ?? 0) * 100);

  return (
    <div className="mt-2">
      <div className="flex justify-between text-[11px] text-slate-400 mb-1">
        <span>ML Late Risk</span>
        <span>
          On Time {onTime}% · Slight {slight}% · Late {late}%
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full overflow-hidden bg-slate-800 flex">
        <div style={{ width: `${onTime}%` }} className="bg-emerald-500" />
        <div style={{ width: `${slight}%` }} className="bg-amber-400" />
        <div style={{ width: `${late}%` }} className="bg-rose-500" />
      </div>
    </div>
  );
}

export function StopTimeline({ bus, watchedStopId, onWatchStop }: StopTimelineProps) {
  const watchedPred: StopPrediction | undefined = bus.predictions.find(
    (p) => p.stop_id === watchedStopId
  );

  const showProximityAlert =
    watchedPred &&
    watchedPred.status !== 'passed' &&
    (watchedPred.remaining_min <= 5.0 || watchedPred.late_status === 'Late');

  return (
    <div className="flex flex-col gap-3">
      {showProximityAlert && watchedPred && (
        <div
          className={`rounded-xl border p-3 text-xs flex items-start gap-2.5 ${
            watchedPred.late_status === 'Late'
              ? 'bg-rose-500/15 border-rose-500/40 text-rose-200'
              : 'bg-sky-500/15 border-sky-500/40 text-sky-200'
          }`}
        >
          <BellRing className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold">
              Alert for {watchedPred.stop_name}
            </div>
            <div className="opacity-90 mt-0.5">
              Bus {bus.bus_number} predicted TOA {formatClock(watchedPred.predicted_toa)} (
              {watchedPred.remaining_min} min away · {watchedPred.late_status})
            </div>
          </div>
        </div>
      )}

      {/* Campus & Next Stop Hero Cards */}
      <div className="grid grid-cols-2 gap-2.5">
        <div className="rounded-xl bg-slate-900/90 border border-slate-800 p-3">
          <div className="text-[11px] uppercase tracking-wider text-slate-400">Next Stop TOA</div>
          {bus.next_stop ? (
            <>
              <div className="text-lg font-bold text-white mt-0.5">
                {bus.next_stop.remaining_min} min
              </div>
              <div className="text-xs text-slate-300 truncate">{bus.next_stop.stop_name}</div>
              <div className="text-[11px] text-slate-400 mt-1">
                ETA {formatClock(bus.next_stop.predicted_toa)} · {bus.next_stop.distance_km} km
              </div>
            </>
          ) : (
            <div className="text-sm text-slate-400 mt-1">Arrived at Campus</div>
          )}
        </div>

        <div className="rounded-xl bg-slate-900/90 border border-slate-800 p-3">
          <div className="text-[11px] uppercase tracking-wider text-slate-400">Campus Arrival</div>
          {bus.campus_prediction ? (
            <>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-lg font-bold text-white">
                  {formatClock(bus.campus_prediction.predicted_toa)}
                </span>
              </div>
              <div className="mt-1">
                <span
                  className={`inline-flex items-center px-2 py-0.5 text-[11px] font-medium rounded-full border ${lateBadgeClasses(
                    bus.campus_prediction.late_status
                  )}`}
                >
                  {bus.campus_prediction.late_status}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                {formatDelay(bus.campus_prediction.predicted_delay_min)}
              </div>
            </>
          ) : (
            <div className="text-sm text-slate-400 mt-1">—</div>
          )}
        </div>
      </div>

      {/* Stop-by-stop ML predictions */}
      <div className="rounded-xl bg-slate-900/80 border border-slate-800 p-3">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Stop-by-Stop ML Predictions
          </h3>
          <span className="text-[11px] text-slate-400">Click bell to watch stop</span>
        </div>

        <div className="space-y-2.5">
          {bus.predictions.map((stop) => {
            const isWatched = watchedStopId === stop.stop_id;
            const isPassed = stop.status === 'passed';
            const isNext = stop.status === 'next';

            return (
              <div
                key={stop.stop_id}
                className={`rounded-lg border p-2.5 transition ${
                  isNext
                    ? 'bg-sky-500/10 border-sky-500/40'
                    : isPassed
                    ? 'bg-slate-950/50 border-slate-800/60 opacity-60'
                    : 'bg-slate-950/70 border-slate-800'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2 min-w-0">
                    {isPassed ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    ) : stop.is_campus ? (
                      <GraduationCap className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
                    ) : (
                      <MapPin
                        className={`w-4 h-4 shrink-0 mt-0.5 ${
                          isNext ? 'text-sky-400' : 'text-slate-400'
                        }`}
                      />
                    )}
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-slate-100 truncate flex items-center gap-1.5">
                        {stop.stop_name}
                        {isNext && (
                          <span className="text-[10px] uppercase px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 font-semibold">
                            Next
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
                        <span className="inline-flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          Sched {formatClock(stop.scheduled_arrival)}
                        </span>
                        {!isPassed && (
                          <span>
                            · TOA <strong className="text-slate-200">{formatClock(stop.predicted_toa)}</strong>
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {!isPassed && (
                      <div className="text-right">
                        <div className="text-xs font-semibold text-white">
                          {stop.remaining_min}m
                        </div>
                        <span
                          className={`inline-block text-[10px] px-1.5 py-0.5 rounded border ${lateBadgeClasses(
                            stop.late_status
                          )}`}
                        >
                          {formatDelay(stop.predicted_delay_min)}
                        </span>
                      </div>
                    )}
                    {!isPassed && (
                      <button
                        type="button"
                        onClick={() => onWatchStop(isWatched ? null : stop.stop_id)}
                        title={isWatched ? 'Stop watching' : 'Alert me for this stop'}
                        className={`p-1.5 rounded-lg border transition cursor-pointer ${
                          isWatched
                            ? 'bg-sky-500/20 border-sky-400 text-sky-300'
                            : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {isWatched ? (
                          <BellRing className="w-3.5 h-3.5" />
                        ) : (
                          <Bell className="w-3.5 h-3.5" />
                        )}
                      </button>
                    )}
                  </div>
                </div>

                {isNext && <ProbabilityBar probs={stop.late_probability} />}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
