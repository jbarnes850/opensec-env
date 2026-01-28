FROM python:3.11-slim

WORKDIR /app

RUN useradd -m -u 1000 user

COPY --chown=user pyproject.toml .
COPY --chown=user server/ server/
COPY --chown=user client/ client/
COPY --chown=user sim/ sim/
COPY --chown=user oracle/ oracle/
COPY --chown=user schemas/ schemas/
COPY --chown=user data/ data/
COPY --chown=user configs/ configs/
COPY --chown=user openenv.yaml .

RUN pip install --no-cache-dir -e .

USER user
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/state')" || exit 1

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
