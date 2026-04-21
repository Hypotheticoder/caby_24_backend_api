# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required by psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create uploads directory so the app doesn't fail on startup
RUN mkdir -p /app/uploads /app/assets

# Expose port 8017 for the FastAPI application
EXPOSE 8017

# Run migrations, then start the API server
CMD ["sh", "-c", "python scripts/wait_for_db.py && alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8017"]