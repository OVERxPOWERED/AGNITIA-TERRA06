# Build from the repo root:  docker build -f backend/Dockerfile -t terra-api .
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TERRA_REPO_ROOT=/app

# System dependencies: libgomp1 for LightGBM, curl/unzip/ca-certificates for release asset fetch
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY ml/pyproject.toml ml/pyproject.toml
COPY ml/terra ml/terra
RUN pip install --no-cache-dir -e ./ml

COPY backend backend
RUN pip install --no-cache-dir -e ./backend

COPY config config
COPY docs docs

# Artifact delivery via GitHub Release asset build args
# Defaults point at the published release asset (public URL + checksum, nothing secret).
# Override with --build-arg when publishing a new bundle (see docs/deployment.md).
# Live weather is read from files the "Prefetch weather" workflow publishes, before Open-Meteo is called.
ENV TERRA_WEATHER_PREFETCH_URL="https://raw.githubusercontent.com/OVERxPOWERED/AGNITIA-TERRA06/weather-data"

ARG ARTIFACT_URL="https://github.com/OVERxPOWERED/AGNITIA-TERRA06/releases/download/artifacts-20261009-b/terra-artifacts-20261009T161221Z.zip"
ARG ARTIFACT_SHA256="58b1eab943e7378a6eb9c80f5e551aa2cc6ff11f9d51b5f821fcbc2b23e68f86"

RUN if [ -n "$ARTIFACT_URL" ]; then \
      echo "Downloading runtime artifacts from ${ARTIFACT_URL}..." && \
      curl -fL --retry 5 -o /tmp/artifacts.zip "$ARTIFACT_URL" && \
      if [ -n "$ARTIFACT_SHA256" ]; then \
        echo "Verifying SHA256 checksum..." && \
        echo "${ARTIFACT_SHA256}  /tmp/artifacts.zip" | sha256sum -c - ; \
      fi && \
      mkdir -p /app/artifacts && \
      unzip -q /tmp/artifacts.zip -d /app/artifacts && \
      rm -f /tmp/artifacts.zip && \
      echo "Artifacts installed successfully into /app/artifacts."; \
    elif [ ! -d "/app/artifacts" ] || [ -z "$(ls -A /app/artifacts 2>/dev/null)" ]; then \
      echo "================================================================================" >&2 && \
      echo "ERROR: ARTIFACT_URL build argument is empty and /app/artifacts is empty." >&2 && \
      echo "Model and forecast artifacts must be supplied at Docker build time via:" >&2 && \
      echo "  --build-arg ARTIFACT_URL=\"https://github.com/OWNER/REPO/releases/download/.../terra-artifacts-....zip\"" >&2 && \
      echo "  (and optional --build-arg ARTIFACT_SHA256=\"<sha256>\")" >&2 && \
      echo "Run 'make bundle' to create the release asset zip and sha256." >&2 && \
      echo "See docs/deployment.md for complete instructions." >&2 && \
      echo "================================================================================" >&2 && \
      exit 1; \
    fi

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
