from config import load_config


def test_load_config_returns_typed_object(sample_config):
    cfg = load_config(sample_config)

    assert cfg.icloud.share_token == "test-token"
    assert cfg.icloud.photo_interval_seconds == 30
    assert cfg.calendars[0].name == "Family"
    assert cfg.weather.provider == "openmeteo"
    assert cfg.display.calendar_days_ahead == 2
