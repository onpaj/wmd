import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatCar } from '../../src/modules/car.ts';

test('formats battery and range rounded to whole numbers', () => {
  // Act
  const view = formatCar({ battery_percent: 52, range_km: 290.29347072, is_charging: false });

  // Assert
  assert.deepEqual(view, { battery: '52 %', range: '290 km', isLow: false });
});

test('shows a dash when range is unknown', () => {
  // Act
  const view = formatCar({ battery_percent: 80, range_km: null, is_charging: false });

  // Assert
  assert.equal(view?.range, '—');
});

test('flags the battery as low below the threshold', () => {
  // Act
  const low = formatCar({ battery_percent: 19, range_km: 90, is_charging: false });
  const ok = formatCar({ battery_percent: 20, range_km: 100, is_charging: false });

  // Assert
  assert.equal(low?.isLow, true);
  assert.equal(ok?.isLow, false);
});

test('returns null when there is no car status', () => {
  // Act
  const view = formatCar(null);

  // Assert
  assert.equal(view, null);
});

test('prefixes the battery with a bolt while charging', () => {
  // Act
  const view = formatCar({ battery_percent: 52, range_km: 290, is_charging: true });

  // Assert
  assert.equal(view?.battery, '⚡52 %');
});
