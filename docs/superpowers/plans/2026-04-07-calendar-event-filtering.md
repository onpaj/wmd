# Calendar Event Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-calendar regex-based event exclusion so events whose titles match any configured pattern are dropped before reaching the frontend.

**Architecture:** Add `exclude_patterns: list[str]` to `CalendarConfig`; compile patterns with `re.IGNORECASE` at the top of `_parse_ics`; skip events whose `summary` matches any pattern. No frontend changes needed.

**Tech Stack:** Python 3.11+, `re` (stdlib), pytest, respx

---

## File Map

| File | Change |
|------|--------|
| `config.py` | Add `exclude_patterns` field to `CalendarConfig`; read `excludePatterns` in `load_config` |
| `sources/calendar.py` | Import `re`; compile patterns in `_parse_ics`; skip matching events |
| `config.example.json` | Add `excludePatterns` example field to the calendar entry |
| `tests/test_config.py` | Add test: `excludePatterns` is loaded into `exclude_patterns` |
| `tests/test_calendar.py` | Add tests: events matching patterns are excluded; non-matching kept; case-insensitive; multiple patterns; recurring events filtered |

---

## Task 1: Config — add `exclude_patterns` field

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
import json


def test_load_config_reads_exclude_patterns(tmp_path):
    data = {
        "icloud": {"shareToken": "t", "photoIntervalSeconds": 30},
        "calendars": [
            {
                "name": "Work",
                "url": "https://example.com/work.ics",
                "color": "#FF0000",
                "excludePatterns": ["^Busy$", "tentative"],
            }
        ],
        "weather": {"provider": "metno", "latitude": 50.0, "longitude": 14.0, "accuweatherApiKey": ""},
        "homeAssistant": {"url": "http://ha.local", "token": "tok", "entities": []},
        "display": {"calendarDaysAhead": 2, "weatherDays": 5},
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))

    from config import load_config
    cfg = load_config(str(config_file))

    assert cfg.calendars[0].exclude_patterns == ["^Busy$", "tentative"]


def test_load_config_exclude_patterns_defaults_to_empty(sample_config):
    from config import load_config
    cfg = load_config(sample_config)

    assert cfg.calendars[0].exclude_patterns == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && pytest tests/test_config.py::test_load_config_reads_exclude_patterns tests/test_config.py::test_load_config_exclude_patterns_defaults_to_empty -v
```

Expected: FAIL — `CalendarConfig` has no `exclude_patterns` attribute.

- [ ] **Step 3: Add `exclude_patterns` to `CalendarConfig` and `load_config`**

In `config.py`, update the `CalendarConfig` dataclass:

```python
@dataclass
class CalendarConfig:
    name: str
    url: str
    color: str
    exclude_patterns: list[str] = field(default_factory=list)
```

In `load_config`, update the calendars list comprehension:

```python
calendars = [
    CalendarConfig(
        name=c["name"],
        url=c["url"],
        color=c["color"],
        exclude_patterns=c.get("excludePatterns", []),
    )
    for c in data.get("calendars", [])
]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: add exclude_patterns field to CalendarConfig"
```

---

## Task 2: Calendar parser — filter events by regex

**Files:**
- Modify: `sources/calendar.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_calendar.py`:

```python
@respx.mock
async def test_exclude_patterns_removes_matching_event():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()
    cfg.calendars[0] = CalendarConfig(name="Test Cal", url=CAL_URL, color="#FF0000", exclude_patterns=["trh"])

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    titles = {e.title for e in events}
    assert "Trh Dka" not in titles
    assert "Celodení akce" in titles


@respx.mock
async def test_exclude_patterns_case_insensitive():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()
    cfg.calendars[0] = CalendarConfig(name="Test Cal", url=CAL_URL, color="#FF0000", exclude_patterns=["TRH"])

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    titles = {e.title for e in events}
    assert "Trh Dka" not in titles


@respx.mock
async def test_exclude_patterns_multiple_patterns():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()
    cfg.calendars[0] = CalendarConfig(name="Test Cal", url=CAL_URL, color="#FF0000", exclude_patterns=["trh", "celodení"])

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    assert events == []


@respx.mock
async def test_exclude_patterns_no_patterns_keeps_all_events():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()
    # exclude_patterns defaults to [] — no filtering

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    assert len(events) == 2


@respx.mock
async def test_exclude_patterns_filters_recurring_events():
    respx.get(RECURRING_URL).mock(return_value=httpx.Response(200, content=RECURRING_ICS))
    cfg = make_config(url=RECURRING_URL, calendar_days_ahead=2)
    cfg.calendars[0] = CalendarConfig(name="Test Cal", url=RECURRING_URL, color="#FF0000", exclude_patterns=["standup"])

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    standup_events = [e for e in events if e.title == "Standup"]
    assert standup_events == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && pytest tests/test_calendar.py::test_exclude_patterns_removes_matching_event tests/test_calendar.py::test_exclude_patterns_case_insensitive tests/test_calendar.py::test_exclude_patterns_multiple_patterns tests/test_calendar.py::test_exclude_patterns_no_patterns_keeps_all_events tests/test_calendar.py::test_exclude_patterns_filters_recurring_events -v
```

Expected: all FAIL — `_parse_ics` does not filter yet.

- [ ] **Step 3: Add regex filtering to `_parse_ics`**

In `sources/calendar.py`, add `import re` at the top of the file (with the other imports).

At the top of `_parse_ics`, after the `events: list[CalendarEvent] = []` line, add:

```python
compiled = [re.compile(p, re.IGNORECASE) for p in cal_cfg.exclude_patterns]
```

Then, in the `for component in cal.walk()` loop, after the line `summary = str(component.get("SUMMARY", ""))`, add:

```python
if compiled and any(rx.search(summary) for rx in compiled):
    continue
```

The full updated function header and filter section should look like this:

```python
def _parse_ics(
    content: bytes,
    cal_cfg: CalendarConfig,
    window_start: datetime,
    window_end: datetime,
) -> list[CalendarEvent]:
    cal = Calendar.from_ical(content)
    events: list[CalendarEvent] = []
    compiled = [re.compile(p, re.IGNORECASE) for p in cal_cfg.exclude_patterns]

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        dtstart_prop = component.get("DTSTART")
        if dtstart_prop is None:
            continue
        raw_start = dtstart_prop.dt

        dtend_prop = component.get("DTEND") or component.get("DUE")
        raw_end = dtend_prop.dt if dtend_prop else raw_start

        all_day = isinstance(raw_start, date) and not isinstance(raw_start, datetime)

        uid = str(component.get("UID", ""))
        summary = str(component.get("SUMMARY", ""))
        location_raw = component.get("LOCATION")
        location = str(location_raw) if location_raw else None

        if compiled and any(rx.search(summary) for rx in compiled):
            continue

        # ... rest of the function unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_calendar.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sources/calendar.py tests/test_calendar.py
git commit -m "feat: filter calendar events by exclude_patterns regex"
```

---

## Task 3: Document the new config field in `config.example.json`

**Files:**
- Modify: `config.example.json`

- [ ] **Step 1: Add `excludePatterns` to the example calendar entry**

In `config.example.json`, update the calendars array to show the new optional field:

```json
"calendars": [
  {
    "name": "Family",
    "url": "https://example.com/calendar.ics",
    "color": "#4CAF50",
    "excludePatterns": []
  }
],
```

- [ ] **Step 2: Commit**

```bash
git add config.example.json
git commit -m "docs: add excludePatterns example to config.example.json"
```

---

## Task 4: Full test suite verification

- [ ] **Step 1: Run all tests**

```bash
source .venv/bin/activate && pytest -v
```

Expected: all tests PASS, no regressions.
