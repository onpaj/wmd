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


def test_load_config_strava_s5_url_parsed(tmp_path):
    custom_url = "https://wss53.strava.cz/WSStravne5_14/WSStravne5.svc"
    data = {
        "icloud": {"shareToken": "t", "photoIntervalSeconds": 30},
        "calendars": [],
        "weather": {"provider": "openmeteo", "latitude": 50.0, "longitude": 14.0},
        "homeAssistant": {"url": "http://ha.local", "token": "tok", "entities": []},
        "display": {"calendarDaysAhead": 2, "weatherDays": 5},
        "strava": {
            "email": "t@e.com",
            "password": "p",
            "s5Url": custom_url,
            "people": [],
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))

    cfg = load_config(str(config_file))

    assert cfg.strava.s5_url == custom_url


def test_load_config_strava_s5_url_defaults_to_none(tmp_path):
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

    assert cfg.strava.s5_url is None


def test_loads_ms365_named_calendars(tmp_path):
    import json
    from config import load_config
    from tests.conftest import SAMPLE_CONFIG

    data = dict(SAMPLE_CONFIG)
    data["ms365"] = {
        "tenantId": "t", "clientId": "c", "clientSecret": "s",
        "users": [],
        "calendars": [
            {
                "email": "ondra@example.com",
                "calendarName": "Work EXT",
                "name": "Blue",
                "color": "#2196F3",
                "excludePatterns": ["Time[\\s]?block"],
                "showAsBusy": True,
            }
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data))

    cfg = load_config(str(p))

    assert len(cfg.ms365.calendars) == 1
    cal = cfg.ms365.calendars[0]
    assert cal.email == "ondra@example.com"
    assert cal.calendar_name == "Work EXT"
    assert cal.name == "Blue"
    assert cal.color == "#2196F3"
    assert cal.exclude_patterns == ["Time[\\s]?block"]
    assert cal.show_as_busy is True


def test_ms365_named_calendars_default_to_empty(tmp_path):
    import json
    from config import load_config
    from tests.conftest import SAMPLE_CONFIG

    data = dict(SAMPLE_CONFIG)
    data["ms365"] = {"tenantId": "t", "clientId": "c", "clientSecret": "s", "users": []}
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data))

    cfg = load_config(str(p))

    assert cfg.ms365.calendars == []


def test_loads_calendar_show_as_busy(tmp_path):
    import json
    from config import load_config
    from tests.conftest import SAMPLE_CONFIG

    data = json.loads(json.dumps(SAMPLE_CONFIG))
    data["calendars"] = [
        {"name": "Work", "url": "https://x/f.ics", "color": "#2196F3", "showAsBusy": True},
        {"name": "Home", "url": "https://y/f.ics", "color": "#4CAF50"},
    ]
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data))

    cfg = load_config(str(p))

    assert cfg.calendars[0].show_as_busy is True
    assert cfg.calendars[1].show_as_busy is False
