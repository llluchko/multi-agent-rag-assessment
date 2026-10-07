FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 HF_HUB_DISABLE_TELEMETRY=1 \
    EMBEDDING_CACHE=/app/.cache/models
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt constraints.txt ./
RUN pip install -r requirements.txt -c constraints.txt
RUN useradd --create-home --uid 1000 demo && mkdir -p /app/.cache && chown -R demo:demo /app
COPY --chown=demo:demo . .
USER demo
EXPOSE 8000 8888
CMD ["python", "-m", "uvicorn", "rag_system.api:app", "--host", "0.0.0.0", "--port", "8000"]
