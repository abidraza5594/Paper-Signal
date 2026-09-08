# PaperSignal API as a container, for App Runner (or any container platform).
#
# The container is stateless: PDFs go to S3 and records to DynamoDB, so an
# instance can be replaced at any moment without losing anything.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so code edits do not invalidate this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY manage_keys.py cleanup.py ./
# The Angular build, produced on the developer machine (it needs ~2 GB to build).
COPY web ./web

# Run as a non-root user.
RUN useradd --create-home --uid 10001 papersignal \
    && mkdir -p /app/data \
    && chown -R papersignal:papersignal /app
USER papersignal

EXPOSE 8000

# App Runner health-checks the port; /api/health needs no credentials.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
