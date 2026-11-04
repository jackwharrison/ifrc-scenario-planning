"""Entry point for gunicorn (Azure App Service) and for running locally."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
