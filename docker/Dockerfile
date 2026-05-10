FROM python:3.12-slim

WORKDIR /app

# pyvalhalla needs system protobuf and other shared libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libprotobuf-dev \
    libsqlite3-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["uvicorn", "cesg_route_search.app:app", "--host", "0.0.0.0", "--port", "8080"]
