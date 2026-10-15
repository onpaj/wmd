import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatNameDay } from '../../src/modules/nameday.ts';

test('shows the single name celebrated on a date', () => {
  // Act
  const label = formatNameDay(new Date(2026, 11, 6));

  // Assert
  assert.equal(label, 'Svátek: Mikuláš');
});

test('joins several names celebrated on the same date', () => {
  // Act
  const label = formatNameDay(new Date(2026, 0, 6));

  // Assert
  assert.equal(label, 'Svátek: Kašpar, Melichar, Baltazar');
});

test('returns an empty label on public holidays with no name', () => {
  // Act
  const label = formatNameDay(new Date(2026, 0, 1));

  // Assert
  assert.equal(label, '');
});

test('covers the leap day', () => {
  // Act
  const label = formatNameDay(new Date(2028, 1, 29));

  // Assert
  assert.equal(label, 'Svátek: Horymír');
});
