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

export interface Meals {
  soup_today: string;
  soup_tomorrow: string;
  lunch_today: string;
  lunch_tomorrow: string;
}

export interface DashboardData {
  photos: Photo[];
  events: CalendarEvent[];
  mini_cal_events: CalendarEvent[];
  weather: WeatherDay[];
  ha_entities: HaEntity[];
  meals: Meals | null;
  outdoor_temp: number | null;
  photo_interval_seconds: number;
  server_time: string;
}
