# Kasa backend for Google Cloud Run.
#   gcloud run deploy kasa-api --source . --region europe-west1
# Debian 12 (bookworm) pinned: it is a supported target for Microsoft's msodbcsql18 packages.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Microsoft ODBC Driver 18 for SQL Server (needed by pyodbc).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg ca-certificates unixodbc \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && . /etc/os-release \
    && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/${VERSION_ID}/prod ${VERSION_CODENAME} main" \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-mssql.txt ./
RUN pip install -r requirements.txt -r requirements-mssql.txt

COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN useradd --create-home --uid 10001 kasa
USER kasa

# Cloud Run injects $PORT. DATABASE_URL falls back to a throwaway SQLite file for demo deploys;
# in prod set it (from Secret Manager) to the mssql+pyodbc URL and AUTO_MIGRATE=false, and run
# `alembic upgrade head` with an admin MIGRATION_DATABASE_URL as a deploy step (Cloud Run job).
ENV PORT=8080 \
    DATABASE_URL=sqlite:////tmp/kasa.db
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
