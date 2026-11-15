# ElderCare Connect API - container for Google Cloud Run (or any container host).
# Secrets are NOT baked in: configure them as Cloud Run env vars / Secret Manager secrets.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# Cloud Run provides $PORT (default 8080). One worker per container: scale with instances,
# and the notification scheduler's MongoDB lease ensures only one instance runs reminder cycles.
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
