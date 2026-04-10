FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for SQLite
RUN mkdir -p /data

# Set environment variables
ENV COLLECTOR_PORT=5600
ENV DB_PATH=/data/logs.db
ENV PYTHONUNBUFFERED=1

EXPOSE 5600

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5600/api/dashboard/summary')" || exit 1

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5600", "--workers", "2", "--timeout", "120", "app:app"]
