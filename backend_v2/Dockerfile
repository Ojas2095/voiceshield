FROM python:3.11-slim

# System deps for scipy / numpy build wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY models/ ./models/

# Create non-root user
RUN useradd -m -u 1000 voiceshield && chown -R voiceshield:voiceshield /app
USER voiceshield

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
