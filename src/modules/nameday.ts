import { NAME_DAYS } from '../data/namedays.ts';

const LABEL_PREFIX = 'Svátek: ';

function dateKey(date: Date): string {
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  return `${mm}-${dd}`;
}

/** Czech name-day label for a local date, or '' on holidays that carry no name. */
export function formatNameDay(date: Date): string {
  const names = NAME_DAYS[dateKey(date)];
  return names ? `${LABEL_PREFIX}${names.join(', ')}` : '';
}
