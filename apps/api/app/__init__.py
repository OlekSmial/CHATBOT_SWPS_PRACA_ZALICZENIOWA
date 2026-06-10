from flask_cors import CORS

from flask import Flask
from dotenv import load_dotenv 

from app.routes.chat import chat_bp
from app.routes.health import health_bp
from app.openalex import openalex_bp
import os


def create_app() -> Flask:
    """Tworzy i konfiguruje aplikację Flask."""
    load_dotenv()

    app = Flask(__name__)

    # Pozwól aplikacji Next.js `web` wywoływać to API z przeglądarki.
    cors_origin = os.environ.get("CORS_ORIGIN", "http://localhost:3000")
    CORS(app, resources={r"/*": {"origins": cors_origin}})

    app.register_blueprint(health_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(openalex_bp, url_prefix='/api/openalex')

    return app
