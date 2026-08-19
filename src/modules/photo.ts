import type { Photo } from '../types';

const ACTIVE_CLASS = 'photo-img--active';

let _interval: ReturnType<typeof setInterval> | null = null;
let _currentIntervalSeconds = 0;
let _photos: Photo[] = [];
let _sourceIds: string[] = [];
let _index = 0;

function shuffle(arr: Photo[]): Photo[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function formatPhotoDate(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return new Intl.DateTimeFormat('cs-CZ', {
    day: 'numeric',
    month: 'numeric',
    year: 'numeric',
  }).format(d);
}

/**
 * Compares against the ids in server order — `_photos` is shuffled, so comparing
 * against it would report a change on every poll and restart the slideshow.
 */
function hasAlbumChanged(data: Photo[]): boolean {
  if (data.length !== _sourceIds.length) return true;
  return data.some((p, i) => p.id !== _sourceIds[i]);
}

/**
 * Loads the next photo into the hidden <img> and cross-fades only once it has
 * decoded, so a partially loaded (or previously shown) image is never revealed.
 */
function showNext(imgA: HTMLImageElement, imgB: HTMLImageElement, dateEl: HTMLElement): void {
  if (_photos.length === 0) return;

  const aIsActive = imgA.classList.contains(ACTIVE_CLASS);
  const active = aIsActive ? imgA : imgB;
  const inactive = aIsActive ? imgB : imgA;

  const next = _photos[_index % _photos.length];
  _index++;

  inactive.onload = () => {
    active.classList.remove(ACTIVE_CLASS);
    inactive.classList.add(ACTIVE_CLASS);
    dateEl.textContent = formatPhotoDate(next.date);
  };
  inactive.onerror = () => {
    console.error(`Failed to load photo ${next.id}; keeping the current one`);
  };
  inactive.src = next.url;
}

function restartTimer(
  imgA: HTMLImageElement,
  imgB: HTMLImageElement,
  dateEl: HTMLElement,
  seconds: number,
): void {
  if (_interval !== null) clearInterval(_interval);
  _currentIntervalSeconds = seconds;
  _interval = setInterval(() => showNext(imgA, imgB, dateEl), seconds * 1000);
}

export function render(data: Photo[], container: HTMLElement, photoIntervalSeconds: number): void {
  if (data.length === 0) return;

  const imgA = container.querySelector<HTMLImageElement>('#photo-a')!;
  const imgB = container.querySelector<HTMLImageElement>('#photo-b')!;
  const dateEl = container.querySelector<HTMLElement>('#photo-date')!;
  imgA.classList.add('photo-img');
  imgB.classList.add('photo-img');

  const albumChanged = hasAlbumChanged(data);
  if (albumChanged) {
    _sourceIds = data.map(p => p.id);
    _photos = shuffle(data);
    _index = 0;
    showNext(imgA, imgB, dateEl);
  }

  // Restarting after a forced swap keeps a full interval before the next one.
  if (albumChanged || photoIntervalSeconds !== _currentIntervalSeconds) {
    restartTimer(imgA, imgB, dateEl, photoIntervalSeconds);
  }
}
