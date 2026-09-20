# Stage 1 — Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --default-timeout=120 --retries=8 --upgrade pip && \
    pip install --no-cache-dir --default-timeout=120 --retries=8 -r requirements.txt

# Stage 2 — Production stage
FROM python:3.11-slim AS production

# Patch OS packages to pick up security fixes not yet baked into the
# upstream python:3.11-slim snapshot (fixes CVE-2026-13221, CVE-2026-42496,
# CVE-2026-8376 in perl-base and similar). Must run as root, before USER switch.
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

COPY main.py .

USER appuser

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
