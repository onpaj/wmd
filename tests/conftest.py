import json
import pytest


SAMPLE_CONFIG = {
    "icloud": {
        "shareToken": "test-token",
        "photoIntervalSeconds": 30,
    },
    "calendars": [
        {
            "name": "Family",
            "url": "https://example.com/calendar.ics",
            "color": "#4CAF50",
        }
    ],
    "weather": {
        "provider": "openmeteo",
        "latitude": 50.07,
        "longitude": 14.43,
    },
    "homeAssistant": {
        "url": "http://homeassistant.local:8123",
        "token": "test-ha-token",
        "entities": [],
    },
    "display": {
        "calendarDaysAhead": 2,
        "weatherDays": 5,
    },
}


@pytest.fixture
def sample_config(tmp_path) -> str:
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(SAMPLE_CONFIG))
    return str(config_file)
