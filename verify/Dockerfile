FROM python:3.11-slim

# Node 18 (Debian bookworm) is sufficient for the Vite 5 production build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt pytest httpx

COPY backend ./backend
COPY frontend ./frontend
COPY verify ./verify

# Pre-install frontend dependencies so the one-shot run needs no network.
RUN cd frontend && npm ci --no-audit --no-fund

RUN chmod +x verify/run-tests.sh

CMD ["verify/run-tests.sh"]
