FROM python:3.13.3-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies (Debian style)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libpq-dev \
    curl \
    build-essential \
    python3-dev \
    && apt-get clean

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy app source code
COPY . .

# start.sh is a script that waits for PostgreSQL to be ready before starting the application
COPY start.sh .
RUN chmod +x start.sh


CMD ["sh", "./start.sh"]
