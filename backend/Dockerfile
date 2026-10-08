# Build from the repo root:  docker build -f backend/Dockerfile -t terra-api .
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TERRA_REPO_ROOT=/app
COPY ml/pyproject.toml ml/pyproject.toml
COPY ml/terra ml/terra
RUN pip install --no-cache-dir -e ./ml
COPY backend backend
RUN pip install --no-cache-dir -e ./backend
COPY config config
COPY docs docs
# data/ and artifacts/ are mounted as volumes (see docker-compose.yml)
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
