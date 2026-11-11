# Programming Learning Agent – Image für API (FastAPI) und Learning Worker.
# Bauen (auf dem Linux-Host, NICHT in Dockhand):
#   docker build -t programming-school-agent:1.0 /Projekte/Festplatten/int0SSD0/agent
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/data

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Persistente Daten (SQLite-Zustand, Lock, Status) liegen in /data (Bind-Mount).
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8090

# Standard: API. Der Worker überschreibt den Befehl: python -m app.worker
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090", "--no-access-log"]
