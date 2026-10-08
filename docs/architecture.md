# TERRA Architecture

TERRA's backend integrates Open-Meteo weather data with a digital twin of the Dewas plant, combining physical heuristics with LightGBM-Quantile models, feeding into a suite of engines (Trust, Dispatch LP, Deviation Shield), and exposing endpoints to a Next.js frontend via FastAPI.

`mermaid
flowchart LR
  subgraph Sources
    PR[Open-Meteo Previous Runs<br/>forecast weather 0/24/48 h]
    AR[Open-Meteo Archive<br/>actual weather]
    LF[Open-Meteo Forecast<br/>live]
    RD[Real data R1-R4<br/>Kaggle plants, SCADA, Grid-India, CEA]
  end
  subgraph ML["ml/terra (Python)"]
    TW[Digital twin<br/>pvlib + windpowerlib + realism]
    CAL[Calibration]
    FR[Framing + features]
    MD[persistence · physics · LightGBM-Q · Chronos-2]
    EN[Ensemble + CQR]
    ENG[Engines: hybrid · trust · alerts · dispatch LP · DSM · what-if · impact]
  end
  KG[Kaggle 2×T4<br/>Chronos-2 inference + LoRA] -.-> MD
  subgraph API["backend (FastAPI)"]
    SCH[Scheduler<br/>live / replay]
    RT[REST + SSE]
    DB[(SQLite + Parquet runs)]
  end
  UI[Next.js control room<br/>10 pages]
  AR --> TW
  RD --> CAL --> TW
  PR --> FR
  TW --> FR --> MD --> EN --> ENG
  LF --> SCH --> ENG --> DB --> RT --> UI
`

