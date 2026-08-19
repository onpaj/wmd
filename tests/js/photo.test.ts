import { test } from 'node:test';
import assert from 'node:assert/strict';
import { FakeContainer } from './fake-dom.ts';
import { mockRandom } from './random.ts';
import type { Photo } from '../../src/types.ts';

const INTERVAL_SECONDS = 15;

function album(count: number, prefix: string): Photo[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `${prefix}${i}`,
    url: `/api/photo/${prefix}${i}`,
    date: `2026-01-${String((i % 28) + 1).padStart(2, '0')}T12:00:00`,
  }));
}

/** Each test gets its own module instance so the module-level slideshow state is isolated. */
async function loadPhotoModule(testCase: string) {
  return import(`../../src/modules/photo.ts?case=${testCase}`);
}

test('keeps showing the same photo when a poll returns an unchanged album', async t => {
  // Arrange
  t.mock.timers.enable({ apis: ['setInterval'] });
  mockRandom(t.mock);
  const { render } = await loadPhotoModule('unchanged');
  const container = new FakeContainer();
  const photos = album(20, 'p');

  render(photos, container as unknown as HTMLElement, INTERVAL_SECONDS);
  container.flushLoads();
  const shownBefore = container.activeSrc;

  // Act — the 60s poll delivers an equal but freshly-allocated list
  render([...photos], container as unknown as HTMLElement, INTERVAL_SECONDS);
  container.flushLoads();

  // Assert
  assert.equal(container.activeSrc, shownBefore);
});

test('only makes the next photo visible once it has finished loading', async t => {
  // Arrange
  t.mock.timers.enable({ apis: ['setInterval'] });
  mockRandom(t.mock);
  const { render } = await loadPhotoModule('load-gated-interval');
  const container = new FakeContainer();

  render(album(20, 'p'), container as unknown as HTMLElement, INTERVAL_SECONDS);
  container.flushLoads();
  const shownBefore = container.activeSrc;

  // Act — the interval fires but the new image has not loaded yet
  t.mock.timers.tick(INTERVAL_SECONDS * 1000);

  // Assert
  assert.equal(container.activeSrc, shownBefore, 'photo must not change before the image loads');
  container.flushLoads();
  assert.notEqual(container.activeSrc, shownBefore, 'photo must change once the image has loaded');
});

test('waits for the image to load when a changed album forces a swap', async t => {
  // Arrange
  t.mock.timers.enable({ apis: ['setInterval'] });
  mockRandom(t.mock);
  const { render } = await loadPhotoModule('load-gated-forced');
  const container = new FakeContainer();

  render(album(20, 'p'), container as unknown as HTMLElement, INTERVAL_SECONDS);
  container.flushLoads();
  const shownBefore = container.activeSrc;

  // Act — a genuinely different album arrives, but its first image has not loaded yet
  render(album(20, 'q'), container as unknown as HTMLElement, INTERVAL_SECONDS);

  // Assert
  assert.equal(container.activeSrc, shownBefore, 'must not reveal an image that is still loading');
  container.flushLoads();
  assert.match(container.activeSrc!, /^\/api\/photo\/q/, 'shows a photo from the new album');
});

test('restarts the swap timer when the album genuinely changes', async t => {
  // Arrange
  t.mock.timers.enable({ apis: ['setInterval'] });
  mockRandom(t.mock);
  const { render } = await loadPhotoModule('timer-restart');
  const container = new FakeContainer();

  render(album(20, 'p'), container as unknown as HTMLElement, INTERVAL_SECONDS);
  container.flushLoads();
  t.mock.timers.tick(10_000);
  container.flushLoads();

  // Act — a genuinely different album arrives 10s into the current cycle
  render(album(20, 'q'), container as unknown as HTMLElement, INTERVAL_SECONDS);
  container.flushLoads();
  const shownAfterChange = container.activeSrc;
  t.mock.timers.tick(10_000);
  container.flushLoads();

  // Assert — the next swap is a full interval after the forced one, not 5s later
  assert.equal(container.activeSrc, shownAfterChange, 'timer must restart on a forced swap');
  t.mock.timers.tick(5_000);
  container.flushLoads();
  assert.notEqual(container.activeSrc, shownAfterChange);
});

test('reveals the capture date only when the photo becomes visible', async t => {
  // Arrange
  t.mock.timers.enable({ apis: ['setInterval'] });
  mockRandom(t.mock);
  const { render } = await loadPhotoModule('capture-date');
  const container = new FakeContainer();

  render(album(20, 'p'), container as unknown as HTMLElement, INTERVAL_SECONDS);
  container.flushLoads();
  const dateBefore = container.dateEl.textContent;

  // Act
  t.mock.timers.tick(INTERVAL_SECONDS * 1000);

  // Assert
  assert.equal(container.dateEl.textContent, dateBefore, 'date must not run ahead of the image');
  container.flushLoads();
  assert.notEqual(container.dateEl.textContent, dateBefore);
});
