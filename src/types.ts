export interface Photo {
  id: string;
  url: string;
}

export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  all_day: boolean;
  calendar_name: string;
  color: string;
  location?: string | null;
}

export interface WeatherDay {
  date: string;
  icon: string;
  temp_high: number;
  temp_low: number;
  precip_percent: number;
}

export interface HaEntity {
  id: string;
  label: string;
  state: string;
  unit: string;
}

export interface StravaPersonStatus {
  name: string;
  color: string | null;
  ordered: boolean | null;   // null = all of this person's accounts failed to fetch
}

export interface StravaDay {
  date: string;              // "YYYY-MM-DD"
  soup: string | null;
  meal: string | null;
  people: StravaPersonStatus[];
}

export interface StravaMeals {
  today: StravaDay | null;
  tomorrow: StravaDay | null;
  breaking_time: string;     // "HH:MM"
}

export interface GardenTemps {
  glasshouse: number | null;
  coop: number | null;
  brooder: number | null;
  glasshouse_humidity: number | null;
  coop_humidity: number | null;
  brooder_humidity: number | null;
}

export interface DashboardData {
  photos: Photo[];
  events: CalendarEvent[];
  mini_cal_events: CalendarEvent[];
  weather: WeatherDay[];
  ha_entities: HaEntity[];
  meals: StravaMeals | null;
  outdoor_temp: number | null;
  garden_temps: GardenTemps | null;
  photo_interval_seconds: number;
  server_time: string;
}
