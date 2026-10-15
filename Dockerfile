FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LABKB_DATA_DIR=/app/data

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install . \
    && useradd --uid 10001 --create-home labkb \
    && mkdir -p /app/data \
    && chown -R labkb:labkb /app/data

USER labkb
EXPOSE 8000
CMD ["python", "-m", "labkb", "--host", "0.0.0.0", "--port", "8000"]
