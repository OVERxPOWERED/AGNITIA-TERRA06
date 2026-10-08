import httpx, pandas as pd
LAT, LON = 22.96, 76.05
base = ["shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation", "cloud_cover", "temperature_2m",
        "relative_humidity_2m", "surface_pressure", "wind_speed_10m", "wind_speed_100m", "wind_direction_100m",
        "precipitation"]
hourly = base + [f"{v}_previous_day{d}" for v in base for d in (1, 2)]
for model in ("ecmwf_ifs025", None):
    params = {"latitude": LAT, "longitude": LON, "start_date": "2024-01-01", "end_date": "2024-01-07",
              "hourly": ",".join(hourly), "wind_speed_unit": "ms", "timezone": "GMT"}
    if model: params["models"] = model
    r = httpx.get("https://previous-runs-api.open-meteo.com/v1/forecast", params=params, timeout=60)
    print(model, r.status_code)
    if r.status_code == 200:
        df = pd.DataFrame(r.json()["hourly"])
        print(df.isna().mean().sort_values().tail(10))       # columns that are mostly empty
a = httpx.get("https://archive-api.open-meteo.com/v1/archive", params={"latitude": LAT, "longitude": LON,
    "start_date": "2024-01-01", "end_date": "2024-01-07", "hourly": ",".join(base), "wind_speed_unit": "ms",
    "timezone": "GMT"}, timeout=60)
print("archive", a.status_code, a.json().get("elevation"))
