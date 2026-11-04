#!/bin/sh
# Startup command for Azure App Service (Linux). App Service sends traffic to port 8000.
gunicorn --bind=0.0.0.0:8000 --workers=1 --threads=4 --timeout=120 --access-logfile=- wsgi:app
