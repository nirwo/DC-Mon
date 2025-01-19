FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV FLASK_APP=/app/run.py
ENV FLASK_ENV=development
ENV PYTHONPATH=/app

EXPOSE 5001

# Set the default command
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5001"]
