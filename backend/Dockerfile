FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Host/port are configurable at runtime via these env vars.
ENV API_HOST=0.0.0.0 \
    API_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import json,os,urllib.request,sys; \
port=os.environ.get('API_PORT','8000'); \
r=urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=2); \
sys.exit(0 if json.load(r).get('status')=='ok' else 1)"

CMD ["sh", "-c", "uvicorn app.main:app --host ${API_HOST} --port ${API_PORT}"]
