FROM python:3.11-slim

WORKDIR /app

COPY ./cloud/ingest_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./cloud/ingest_api/app /app/app
COPY ./analytics /app/analytics

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
