import { Photo } from '../types';

let _interval: ReturnType<typeof setInterval> | null = null;
let _currentIntervalSeconds = 0;
let _photos: Photo[] = [];
let _index = 0;

function shuffle(arr: Photo[]): Photo[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function swapActive(imgA: HTMLImageElement, imgB: HTMLImageElement): void {
  const aIsActive = imgA.classList.contains('photo-img--active');
  const inactive = aIsActive ? imgB : imgA;
  const active = aIsActive ? imgA : imgB;

  const next = _photos[_index % _photos.length];
  _index++;

  inactive.onload = () => {
    active.classList.remove('photo-img--active');
    inactive.classList.add('photo-img--active');
  };
  inactive.src = next.url;
}

export function render(data: Photo[], container: HTMLElement, photoIntervalSeconds: number): void {
  if (data.length === 0) return;

  const imgA = container.querySelector<HTMLImageElement>('#photo-a')!;
  const imgB = container.querySelector<HTMLImageElement>('#photo-b')!;
  imgA.classList.add('photo-img');
  imgB.classList.add('photo-img');

  const photosChanged = data !== _photos && (
    data.length !== _photos.length ||
    data.some((p, i) => p.id !== _photos[i]?.id)
  );

  if (photosChanged) {
    _photos = shuffle(data);
    _index = 0;
    // Set first photo immediately
    imgA.src = _photos[0].url;
    imgA.classList.add('photo-img--active');
    imgB.classList.remove('photo-img--active');
    _index = 1;
  }

  if (photoIntervalSeconds !== _currentIntervalSeconds) {
    if (_interval !== null) clearInterval(_interval);
    _currentIntervalSeconds = photoIntervalSeconds;
    _interval = setInterval(() => swapActive(imgA, imgB), photoIntervalSeconds * 1000);
  }
}
