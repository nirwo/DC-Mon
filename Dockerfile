FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV FLASK_APP=app
ENV FLASK_ENV=development
ENV FLASK_RUN_PORT=5001

EXPOSE 5001

CMD ["bash", "-c", "python app/migrate.py && python -m flask run --host=0.0.0.0 --port=5001"]
