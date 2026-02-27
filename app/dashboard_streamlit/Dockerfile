FROM python:3.11-slim

WORKDIR /app

COPY ./app/dashboard_streamlit/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./app/dashboard_streamlit /app/dashboard_streamlit
COPY ./analytics /app/analytics

ENV PYTHONPATH=/app

CMD ["streamlit", "run", "/app/dashboard_streamlit/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
