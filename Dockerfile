FROM python:3.12.7-slim-bookworm

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml README.md requirements.lock ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
COPY agents/signal-intelligence ./agents/signal-intelligence
ENV SIGNAL_INTELLIGENCE_DIR=/app/agents/signal-intelligence
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    && pip install --no-cache-dir --no-deps .

RUN useradd --create-home --uid 10001 signalscout
USER signalscout

CMD ["uvicorn", "signalscout.web:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
