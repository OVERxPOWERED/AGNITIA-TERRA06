# data/
Nothing in here is committed except this README, .gitkeep files and data/samples/.
- raw/        cached Open-Meteo JSON responses (created by `terra fetch-weather`)
- external/   real datasets R1–R4 downloaded by hand (see IMPLEMENTATION_ROADMAP.md Phase 2); each subfolder has its own README with source, licence and download date
- interim/    aligned weather tables, cleaned real data
- processed/  dataset.parquet and framed_*.parquet (model inputs)
- samples/    3-week sample used by tests (small, committed). Note: `data/samples/dataset_sample.parquet` is a SYNTHETIC offline test fixture used strictly for unit testing, not real data.
