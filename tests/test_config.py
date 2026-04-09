import json
from config import load_config


def test_load_config_returns_typed_object(sample_config):
    cfg = load_config(sample_config)

    assert cfg.icloud.share_token == "test-token"
    assert cfg.icloud.photo_interval_seconds == 30
    assert cfg.calendars[0].name == "Family"
    assert cfg.weather.provider == "openmeteo"
    assert cfg.display.calendar_days_ahead == 2


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
        "weather": {"provider": "metno", "latitude": 50.0, "longitude": 14.0},
        "homeAssistant": {"url": "http://ha.local", "token": "tok", "entities": []},
        "display": {"calendarDaysAhead": 2, "weatherDays": 5},
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))

    cfg = load_config(str(config_file))

    assert cfg.calendars[0].exclude_patterns == ["^Busy$", "tentative"]


def test_load_config_exclude_patterns_defaults_to_empty(sample_config):
    cfg = load_config(sample_config)

    assert cfg.calendars[0].exclude_patterns == []


def test_load_config_parses_strava_block(tmp_path):
    data = {
        "icloud": {"shareToken": "t", "photoIntervalSeconds": 30},
        "calendars": [],
        "weather": {"provider": "openmeteo", "latitude": 50.0, "longitude": 14.0},
        "homeAssistant": {"url": "http://ha.local", "token": "tok", "entities": []},
        "display": {"calendarDaysAhead": 2, "weatherDays": 5},
        "strava": {
            "email": "test@example.com",
            "password": "secret",
            "canteenNumber": "1019",
            "breakingTime": "13:00",
            "people": [
                {"name": "Alice", "color": "#4CAF50", "accounts": ["alice.test"]},
                {"name": "Bob",   "color": "#2196F3", "accounts": ["bob.test1", "bob.test2"]},
            ],
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))

    cfg = load_config(str(config_file))

    assert cfg.strava is not None
    assert cfg.strava.email == "test@example.com"
    assert cfg.strava.canteen_number == "1019"
    assert cfg.strava.breaking_time == "13:00"
    assert len(cfg.strava.people) == 2
    assert cfg.strava.people[0].name == "Alice"
    assert cfg.strava.people[0].accounts == ["alice.test"]
    assert cfg.strava.people[1].name == "Bob"
    assert cfg.strava.people[1].accounts == ["bob.test1", "bob.test2"]


def test_load_config_strava_absent_when_not_configured(sample_config):
    cfg = load_config(sample_config)
    assert cfg.strava is None


def test_load_config_strava_breaking_time_defaults_to_1230(tmp_path):
    data = {
        "icloud": {"shareToken": "t", "photoIntervalSeconds": 30},
        "calendars": [],
        "weather": {"provider": "openmeteo", "latitude": 50.0, "longitude": 14.0},
        "homeAssistant": {"url": "http://ha.local", "token": "tok", "entities": []},
        "display": {"calendarDaysAhead": 2, "weatherDays": 5},
        "strava": {
            "email": "t@e.com",
            "password": "p",
            "people": [],
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))

    cfg = load_config(str(config_file))

    assert cfg.strava.breaking_time == "12:30"
    assert cfg.strava.canteen_number == "1019"
