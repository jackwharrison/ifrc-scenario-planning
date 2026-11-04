# Optional: only needed if you run the app as a container (for example Azure Container Apps)
# instead of a plain App Service web app.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home appuser && mkdir -p /data && chown appuser /data
USER appuser
ENV DATABASE_PATH=/data/app.db
EXPOSE 8000
CMD ["gunicorn", "--bind=0.0.0.0:8000", "--workers=1", "--threads=4", "--timeout=120", "--access-logfile=-", "wsgi:app"]
