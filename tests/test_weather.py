from outfit_recommender.weather import weather_code_to_condition


def test_weather_code_to_condition_maps_common_codes() -> None:
    assert weather_code_to_condition(0) == "clear"
    assert weather_code_to_condition(3) == "cloudy"
    assert weather_code_to_condition(61) == "rain"
    assert weather_code_to_condition(71) == "snow"
    assert weather_code_to_condition(95) == "storm"


def test_weather_code_to_condition_handles_unknown_values() -> None:
    assert weather_code_to_condition(None) == "clear"
    assert weather_code_to_condition("bad") == "clear"
