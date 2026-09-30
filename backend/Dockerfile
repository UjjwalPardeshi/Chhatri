# Chhatri backend image (SPEC §2, §21, §23).
#
# Build context is backend/ (see backend/.dockerignore). Python 3.12 slim, runs as a non-root user,
# serves the ASGI factory `chhatri.api.app:create_app` on :8000. The package is installed in editable
# mode so `chhatri.config.BACKEND_DIR` is /app and the committed inputs (/app/data) and generated
# artefacts (/app/artifacts: model/, calibration.json, backtest/, premiums.json, MANIFEST.json) are found
# exactly where the code expects them (binding decision B6). The image never trains or rebuilds
# artefacts: run `make data` on the host first, then rebuild the image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Kolkata \
    CHHATRI_DATA_DIR=/app/data \
    CHHATRI_VAR_DIR=/app/var

# libgomp1: OpenMP runtime the LightGBM wheel links against; tzdata: Asia/Kolkata for zoneinfo.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgomp1 tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 chhatri \
    && useradd --system --uid 10001 --gid chhatri --home-dir /app --shell /usr/sbin/nologin chhatri

WORKDIR /app

# Dependencies first (cached until pyproject.toml changes): exactly [project].dependencies.
COPY pyproject.toml README.md ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" \
        > /tmp/requirements.txt \
    && pip install --requirement /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY chhatri ./chhatri
COPY scripts ./scripts
COPY data ./data
COPY artifacts ./artifacts
RUN pip install --no-deps --editable . \
    && mkdir -p /app/var \
    && chown chhatri:chhatri /app/var

USER chhatri

EXPOSE 8000

# stdlib only (no requests/curl in the image): exit 0 on HTTP 200 from /api/health.
HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"]

CMD ["uvicorn", "--factory", "chhatri.api.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
