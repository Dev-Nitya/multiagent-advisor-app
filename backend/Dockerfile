FROM python:3.11-slim

# Install minimal tools required for healthchecks / debugging
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copy only requirements first to leverage Docker cache
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt || true

# Copy the rest of the backend source
COPY . /app

EXPOSE 8000

# Default command - local development with autoreload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]