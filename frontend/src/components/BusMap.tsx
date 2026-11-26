import { useEffect } from 'react';
import L from 'leaflet';
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet';
import type { BusSummary, Route } from '../types';

interface BusMapProps {
  routes: Route[];
  buses: BusSummary[];
  selectedBusId: number | null;
  onSelectBus: (busId: number) => void;
}

function createBusDivIcon(bus: BusSummary, isSelected: boolean): L.DivIcon {
  const status = bus.campus_prediction?.late_status ?? 'On Time';
  const ringColor =
    status === 'Late' ? '#f43f5e' : status === 'Slightly Late' ? '#f59e0b' : '#10b981';

  return L.divIcon({
    className: 'bus-marker-icon',
    iconSize: [74, 34],
    iconAnchor: [37, 17],
    html: `
      <div style="
        display:flex;
        align-items:center;
        gap:5px;
        padding:4px 8px;
        border-radius:9999px;
        background:${isSelected ? '#0284c7' : '#0f172a'};
        border:2px solid ${isSelected ? '#ffffff' : ringColor};
        box-shadow:0 4px 14px rgba(0,0,0,0.45);
        color:#f8fafc;
        font-size:11px;
        font-weight:700;
        white-space:nowrap;
      ">
        <span style="width:8px;height:8px;border-radius:9999px;background:${ringColor};display:inline-block;"></span>
        <span>${bus.bus_number}</span>
      </div>
    `,
  });
}

function MapFocusHandler({ selectedBus }: { selectedBus: BusSummary | undefined }) {
  const map = useMap();

  useEffect(() => {
    if (selectedBus) {
      map.panTo([selectedBus.current_lat, selectedBus.current_lon], { animate: true });
    }
  }, [selectedBus?.id]);

  return null;
}

export function BusMap({ routes, buses, selectedBusId, onSelectBus }: BusMapProps) {
  const selectedBus = buses.find((b) => b.id === selectedBusId) ?? buses[0];
  const center: [number, number] = selectedBus
    ? [selectedBus.current_lat, selectedBus.current_lon]
    : [12.9352, 77.6245];

  return (
    <div className="relative h-full w-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-900">
      <MapContainer center={center} zoom={12} className="h-full w-full z-0">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <MapFocusHandler selectedBus={selectedBus} />

        {/* Route Polylines & Stops */}
        {routes.map((route) => {
          const isSelectedRoute = selectedBus?.route_id === route.id;
          const positions = route.stops.map((s) => [s.lat, s.lon] as [number, number]);

          return (
            <div key={route.id}>
              <Polyline
                positions={positions}
                pathOptions={{
                  color: route.color,
                  weight: isSelectedRoute ? 5 : 3,
                  opacity: isSelectedRoute ? 0.9 : 0.35,
                  dashArray: isSelectedRoute ? undefined : '6 6',
                }}
              />
              {route.stops.map((stop) => (
                <CircleMarker
                  key={stop.id}
                  center={[stop.lat, stop.lon]}
                  radius={stop.is_campus ? 8 : isSelectedRoute ? 5 : 3.5}
                  pathOptions={{
                    color: stop.is_campus ? '#ffffff' : route.color,
                    fillColor: stop.is_campus ? '#0ea5e9' : '#0f172a',
                    fillOpacity: 1,
                    weight: stop.is_campus ? 3 : 2,
                  }}
                >
                  <Tooltip direction="top" offset={[0, -6]}>
                    <div className="text-xs font-medium">
                      {stop.is_campus ? 'Campus: ' : ''}
                      {stop.name} ({route.code})
                    </div>
                  </Tooltip>
                </CircleMarker>
              ))}
            </div>
          );
        })}

        {/* Live Bus Markers */}
        {buses.map((bus) => {
          const isSelected = bus.id === selectedBus?.id;
          return (
            <Marker
              key={bus.id}
              position={[bus.current_lat, bus.current_lon]}
              icon={createBusDivIcon(bus, isSelected)}
              eventHandlers={{
                click: () => onSelectBus(bus.id),
              }}
            >
              <Popup>
                <div className="text-slate-900 min-w-[180px] text-xs space-y-1">
                  <div className="font-bold text-sm">
                    {bus.bus_number} · {bus.route_name}
                  </div>
                  <div>Driver: {bus.driver_name}</div>
                  <div>
                    Speed: <strong>{bus.current_speed_kmh} km/h</strong> · Occupancy:{' '}
                    <strong>{bus.occupancy_pct}%</strong>
                  </div>
                  {bus.next_stop && (
                    <div className="pt-1 border-t border-slate-200">
                      Next: <strong>{bus.next_stop.stop_name}</strong> ({bus.next_stop.remaining_min} min)
                    </div>
                  )}
                  {bus.campus_prediction && (
                    <div>
                      Campus Status: <strong>{bus.campus_prediction.late_status}</strong>
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      {/* Map Legend Overlay */}
      <div className="absolute bottom-3 left-3 z-[400] bg-slate-950/85 backdrop-blur border border-slate-800 rounded-xl px-3 py-2 text-[11px] text-slate-300 flex items-center gap-3">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> On Time
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400" /> Slightly Late
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500" /> Late
        </span>
      </div>
    </div>
  );
}
