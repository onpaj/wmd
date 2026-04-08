# Calendar Event Filtering Design

**Date:** 2026-04-07
**Status:** Approved

## Summary

Add per-calendar regex-based event exclusion to the WMD dashboard. Each calendar in `config.json` can declare a list of regex patterns; any event whose title matches one of those patterns is silently dropped before it reaches the frontend.

## Config Schema

Add an optional `excludePatterns` array to any entry in the `calendars` list:

```json
{
  "name": "Family",
  "url": "https://example.com/family.ics",
  "color": "#4CAF50",
  "excludePatterns": ["^Busy$", "tentative"]
}
```

- `excludePatterns` is optional; omitting it (or setting it to `[]`) disables filtering for that calendar.
- Applies only to the main `calendars` list. The `miniCalendar` feed is unaffected.

## Backend Changes

### `config.py` — `CalendarConfig`

Add `exclude_patterns: list[str]` with an empty-list default:

```python
@dataclass
class CalendarConfig:
    name: str
    url: str
    color: str
    exclude_patterns: list[str] = field(default_factory=list)
```

Update `load_config` to read the new field:

```python
CalendarConfig(
    name=c["name"],
    url=c["url"],
    color=c["color"],
    exclude_patterns=c.get("excludePatterns", []),
)
```

### `sources/calendar.py` — `_parse_ics`

Compile patterns once at the top of the function, then skip matching events in both the single-occurrence and recurring branches:

```python
import re

compiled = [re.compile(p, re.IGNORECASE) for p in cal_cfg.exclude_patterns]

# after extracting summary:
if any(rx.search(summary) for rx in compiled):
    continue
```

Matching uses `re.search` (substring match) and `re.IGNORECASE`. Patterns follow standard Python `re` syntax.

## Behaviour Details

- **Match semantics:** `re.search` — pattern can match anywhere in the title, not just the start.
- **Case sensitivity:** always case-insensitive (`re.IGNORECASE`).
- **Invalid regex:** a bad pattern in `excludePatterns` will raise `re.error` at startup when the config is first used; this surfaces clearly rather than silently failing.
- **Recurring events:** filtering applies to every occurrence individually (same title check).
- **Frontend:** no changes required — excluded events never appear in `/api/data`.

## Out of Scope

- Include-only (whitelist) mode.
- Filtering on fields other than event title (e.g. location, description).
- Mini-calendar filtering.
- Per-pattern case-sensitivity overrides.
