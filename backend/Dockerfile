# Dockerfile for LLMUD Backend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy mud_client package
COPY mud_client/ ./mud_client/
RUN pip install -e ./mud_client/

# Copy backend code
COPY backend/ ./backend/
COPY strategy.md ./

# Copy strategy file to expected location
WORKDIR /app/backend

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
