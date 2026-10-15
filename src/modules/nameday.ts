import { NAME_DAYS } from '../data/namedays.ts';
import type { FavoriteName } from '../types';

export interface NameDayPart {
  text: string;
  isFavorite: boolean;
}

function dateKey(date: Date): string {
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  return `${mm}-${dd}`;
}

/** Folds case and diacritics so a config "Ondrej" matches the calendar's "Ondřej". */
function normalize(name: string): string {
  return name.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();
}

function toPart(calendarName: string, favorites: readonly FavoriteName[]): NameDayPart {
  const match = favorites.find(f => normalize(f.name_day) === normalize(calendarName));
  if (!match) return { text: calendarName, isFavorite: false };
  // A favorite celebrating its own name keeps the calendar spelling (with diacritics).
  const isOwnNameDay = normalize(match.name) === normalize(calendarName);
  return { text: isOwnNameDay ? calendarName : match.name, isFavorite: true };
}

/** Names celebrated on a local date, favorites marked; empty on holidays that carry no name. */
export function nameDayParts(date: Date, favorites: readonly FavoriteName[]): NameDayPart[] {
  const names = NAME_DAYS[dateKey(date)] ?? [];
  return names.map(name => toPart(name, favorites));
}
