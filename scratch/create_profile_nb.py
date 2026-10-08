import nbformat as nbf
nb = nbf.v4.new_notebook()

code_imports = '''import pandas as pd, matplotlib.pyplot as plt
from terra.paths import DATA_INTERIM
# Plotting setup
plt.style.use("seaborn-v0_8-whitegrid")
'''

md_1 = '''### R1 Kaggle Solar (Plant 1)
- Data has clear daytime generation patterns.
- AC power scales consistently with irradiation.
- No generation during night as expected.
'''

code_1 = '''df_solar = pd.read_parquet(DATA_INTERIM / 'real' / 'kaggle_solar_p1.parquet')
df_solar['ac_mw'].iloc[:24*7].plot(title='Solar AC MW - 1 Week', figsize=(10,4))
plt.show()

df_solar.groupby(df_solar.index.tz_convert('Asia/Kolkata').hour)['ac_mw'].mean().plot(title='Mean AC MW by IST Hour', figsize=(6,3))
plt.show()
'''

md_2 = '''### R2 Wind Turbine SCADA
- Power curve follows expected cubic shape until rated speed.
- Cut-in and cut-out behaviors are visible.
- Consistent day-night variations observed.
'''

code_2 = '''df_wind = pd.read_parquet(DATA_INTERIM / 'real' / 'wind_scada.parquet')
df_wind['power_kw'].iloc[:24*7].plot(title='Wind Power kW - 1 Week', figsize=(10,4))
plt.show()

df_wind.groupby(df_wind.index.tz_convert('Asia/Kolkata').hour)['power_kw'].mean().plot(title='Mean Power by IST Hour', figsize=(6,3))
plt.show()

df_wind.plot.scatter(x='ws_ms', y='power_kw', s=1, alpha=0.1, title='Wind Speed vs Power', figsize=(6,4))
plt.show()
'''

md_3 = '''### R3 India Hourly
- Demand exhibits distinct morning and evening peaks.
- Evening peak is typically higher.
- Seasonality matches Indian grid behavior.
'''

code_3 = '''df_india = pd.read_parquet(DATA_INTERIM / 'real' / 'india_hourly.parquet')
df_india['demand_mw'].iloc[:24*7].plot(title='India Demand MW - 1 Week', figsize=(10,4))
plt.show()

df_india.groupby(df_india.index.tz_convert('Asia/Kolkata').hour)['demand_mw'].mean().plot(title='Mean Demand by IST Hour', figsize=(6,3))
plt.show()
'''

nb['cells'] = [
    nbf.v4.new_code_cell(code_imports),
    nbf.v4.new_markdown_cell(md_1),
    nbf.v4.new_code_cell(code_1),
    nbf.v4.new_markdown_cell(md_2),
    nbf.v4.new_code_cell(code_2),
    nbf.v4.new_markdown_cell(md_3),
    nbf.v4.new_code_cell(code_3),
]
with open('notebooks/02_real_profile.ipynb', 'w') as f:
    nbf.write(nb, f)
