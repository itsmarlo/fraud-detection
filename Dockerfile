FROM python:3.11-slim

ARG PIP_TRUSTED_HOSTS=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Add organization-specific root certificates placed in certs/ to the image.
COPY certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates

COPY requirements.txt .
RUN if [ -n "$PIP_TRUSTED_HOSTS" ]; then \
      pip install --no-cache-dir $PIP_TRUSTED_HOSTS -r requirements.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .
RUN mkdir -p storage/uploads

EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
