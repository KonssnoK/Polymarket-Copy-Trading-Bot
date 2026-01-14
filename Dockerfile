# Python image for Polymarket Copy Trading Bot
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends dumb-init \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml setup.cfg ./
COPY polymarket_copy_trading_bot ./polymarket_copy_trading_bot

RUN pip install --no-cache-dir .

RUN useradd -m -u 1001 appuser
RUN chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["dumb-init", "--"]
CMD ["python", "-m", "polymarket_copy_trading_bot"]

