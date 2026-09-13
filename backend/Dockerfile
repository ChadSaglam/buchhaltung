# Two stages (B-41): build wheels with a compiler, run without one, as a non-root user.
FROM python:3.13-slim AS build
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app
COPY --from=build /install /usr/local
COPY . .
RUN mkdir -p /app/data && chmod +x /app/scripts/migrate-and-run.sh && chown -R app:app /app
USER app

# The ENTRYPOINT migrates, then execs CMD. The worker service overrides the
# ENTRYPOINT so only the API migrates (see docker-compose.yml).
ENTRYPOINT ["/app/scripts/migrate-and-run.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
