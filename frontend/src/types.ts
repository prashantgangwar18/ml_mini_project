export type LateStatus = 'On Time' | 'Slightly Late' | 'Late';
export type WeatherType = 'Clear' | 'Cloudy' | 'Rain' | 'Fog';
export type TrafficType = 'Low' | 'Moderate' | 'Heavy';

export interface Stop {
  id: number;
  route_id: number;
  name: string;
  sequence_order: number;
  lat: number;
  lon: number;
  scheduled_offset_min: number;
  is_campus: boolean;
}

export interface Route {
  id: number;
  code: string;
  name: string;
  color: string;
  direction: string;
  description: string;
  stops: Stop[];
}

export interface StopPrediction {
  stop_id: number;
  stop_name: string;
  sequence_order: number;
  lat: number;
  lon: number;
  is_campus: boolean;
  status: 'passed' | 'next' | 'upcoming';
  scheduled_arrival: string;
  predicted_toa: string;
  remaining_min: number;
  predicted_delay_min: number;
  late_status: LateStatus;
  late_probability: Record<string, number>;
  distance_km: number;
}

export interface BusSummary {
  id: number;
  bus_number: string;
  driver_name: string;
  capacity: number;
  occupancy_pct: number;
  route_id: number;
  route_code: string;
  route_name: string;
  route_color: string;
  status: string;
  current_lat: number;
  current_lon: number;
  current_speed_kmh: number;
  heading: number;
  current_stop_seq: number;
  last_updated: string;
  weather: WeatherType;
  traffic_level: TrafficType;
  next_stop: StopPrediction | null;
  campus_prediction: StopPrediction | null;
  predictions: StopPrediction[];
}

export interface SimulatorStatus {
  running: boolean;
  weather: WeatherType;
  traffic_level: TrafficType;
  speed_multiplier: number;
  tick_count: number;
}

export interface MLMetrics {
  trained_at: string;
  dataset: {
    total_samples: number;
    total_trips: number;
    train_samples: number;
    val_samples: number;
    test_samples: number;
    class_distribution: Record<string, number>;
  };
  toa_models: {
    heuristic_baseline: { mae_min: number; rmse_min: number; r2: number };
    ridge_regression: { mae_min: number; rmse_min: number; r2: number };
    lightgbm_toa: { mae_min: number; rmse_min: number; r2: number };
  };
  delay_regression: { mae_min: number; rmse_min: number; r2: number };
  late_classification: { accuracy: number; macro_f1: number };
  feature_importance: { feature: string; importance: number }[];
}

export interface AdminOverview {
  fleet: {
    total_buses: number;
    active_buses: number;
    on_time: number;
    slightly_late: number;
    late: number;
    telemetry_logs_count: number;
  };
  route_delays: {
    route_code: string;
    route_name: string;
    color: string;
    avg_delay_min: number;
    active_buses: number;
  }[];
  simulator: SimulatorStatus;
}
