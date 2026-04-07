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
        "weather": {"provider": "metno", "latitude": 50.0, "longitude": 14.0, "accuweatherApiKey": ""},
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
