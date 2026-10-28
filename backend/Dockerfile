FROM python:3.14-slim AS dependencias
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /src
COPY pyproject.toml .
COPY app app
RUN pip install .

FROM python:3.14-slim
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ML_ARQUIVO_TOKEN=/home/zpektral/.ml-token.json \
    IPS_PROXY_CONFIAVEIS=127.0.0.1
RUN useradd --create-home --uid 10001 zpektral
COPY --from=dependencias /opt/venv /opt/venv
WORKDIR /srv
COPY alembic.ini .
COPY migrations migrations
USER zpektral
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/saude', timeout=2)"]
CMD ["sh", "-c", "[ -z \"$DATABASE_URL\" ] || alembic upgrade head; exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"$IPS_PROXY_CONFIAVEIS\" --no-access-log"]
