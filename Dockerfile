FROM python:3.11-slim
WORKDIR /app

# Install system dependencies for pyvalhalla
RUN apt-get update && apt-get install -y --no-install-recommends \
    libprotobuf-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[server]"

COPY src/ src/
COPY scripts/ scripts/

ENV TOKYO_VALHALLA_CONFIG=/data/valhalla/valhalla.host.json
EXPOSE 8000

CMD ["uvicorn", "cesg_route_search.server:app", "--host", "0.0.0.0", "--port", "8000"]
