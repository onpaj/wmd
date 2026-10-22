import { test } from 'node:test';
import assert from 'node:assert/strict';
import { statusClass } from '../../src/modules/calendar.ts';

test('adds no modifier class for busy events', () => {
  // Act
  const cls = statusClass('busy');

  // Assert
  assert.equal(cls, null);
});

test('marks tentative and free events with their own modifier class', () => {
  // Act
  const tentative = statusClass('tentative');
  const free = statusClass('free');

  // Assert
  assert.equal(tentative, 'cal-event--tentative');
  assert.equal(free, 'cal-event--free');
});

test('treats a missing status as busy', () => {
  // Act
  const cls = statusClass(undefined);

  // Assert
  assert.equal(cls, null);
});
