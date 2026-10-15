import { test } from 'node:test';
import assert from 'node:assert/strict';
import { nameDayParts } from '../../src/modules/nameday.ts';

const plain = (text: string) => ({ text, isFavorite: false });
const favorite = (text: string) => ({ text, isFavorite: true });

test('lists the single name celebrated on a date', () => {
  // Act
  const parts = nameDayParts(new Date(2026, 11, 6), []);

  // Assert
  assert.deepEqual(parts, [plain('Mikuláš')]);
});

test('lists every name celebrated on the same date', () => {
  // Act
  const parts = nameDayParts(new Date(2026, 0, 6), []);

  // Assert
  assert.deepEqual(parts, [plain('Kašpar'), plain('Melichar'), plain('Baltazar')]);
});

test('returns nothing on public holidays with no name', () => {
  // Act
  const parts = nameDayParts(new Date(2026, 0, 1), []);

  // Assert
  assert.deepEqual(parts, []);
});

test('covers the leap day', () => {
  // Act
  const parts = nameDayParts(new Date(2028, 1, 29), []);

  // Assert
  assert.deepEqual(parts, [plain('Horymír')]);
});

test('marks a favorite name, ignoring case and diacritics', () => {
  // Arrange
  const favorites = [{ name: 'ondrej', name_day: 'ondrej' }];

  // Act
  const parts = nameDayParts(new Date(2026, 10, 30), favorites);

  // Assert
  assert.deepEqual(parts, [favorite('Ondřej')]);
});

test('shows a favorite in place of the calendar name whose day it shares', () => {
  // Arrange
  const favorites = [{ name: 'Ileana', name_day: 'Ilona' }];

  // Act
  const parts = nameDayParts(new Date(2026, 0, 20), favorites);

  // Assert
  assert.deepEqual(parts, [favorite('Ileana'), plain('Sebastián')]);
});

test('leaves names alone when no favorite matches', () => {
  // Arrange
  const favorites = [{ name: 'Petr', name_day: 'Petr' }];

  // Act
  const parts = nameDayParts(new Date(2026, 9, 15), favorites);

  // Assert
  assert.deepEqual(parts, [plain('Tereza'), plain('Terezie')]);
});
