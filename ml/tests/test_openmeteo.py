from terra.data.openmeteo import OpenMeteoClient, month_chunks


def test_month_chunks_cover_range():
    ch = month_chunks("2024-01-15", "2024-03-02")
    assert ch == [("2024-01-15", "2024-01-31"), ("2024-02-01", "2024-02-29"), ("2024-03-01", "2024-03-02")]


def test_to_frame_parses_utc_and_renames():
    payload = {"hourly": {"time": ["2024-01-01T00:00", "2024-01-01T01:00"],
                          "shortwave_radiation": [0, 10], "wind_speed_100m_previous_day1": [5.0, 6.0]}}
    df = OpenMeteoClient.to_frame(payload, {"shortwave_radiation": "act_ghi",
                                            "wind_speed_100m_previous_day1": "fx1_ws100"})
    assert str(df.index.tz) == "UTC"
    assert list(df.columns) == ["act_ghi", "fx1_ws100"]
    assert df["fx1_ws100"].iloc[1] == 6.0
