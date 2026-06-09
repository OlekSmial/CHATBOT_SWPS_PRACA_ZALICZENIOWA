"""Endpoint czatu — oparty na API Google Gemini."""

from flask import Blueprint, current_app, jsonify, request
from google.genai import errors

from app.claude import generate_reply

chat_bp = Blueprint("chat", __name__)


@chat_bp.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") if isinstance(data.get("history"), list) else None

    if not message:
        return jsonify(error="Pole „message” jest wymagane i nie może być puste"), 400

    try:
        reply = generate_reply(message, history)
    except errors.APIError as exc:
        # Błędy od Google Gemini
        if exc.code in (401, 403):
            return jsonify(error="Błąd uwierzytelniania API Gemini — sprawdź GEMINI_API_KEY"), 502
        elif exc.code == 429:
            return jsonify(error="Przekroczono limit zapytań API Gemini — spróbuj ponownie za chwilę"), 429
        else:
            current_app.logger.exception("Gemini API error")
            return jsonify(error=f"Błąd API Gemini: {exc.message}"), 502
    except Exception as exc:
        current_app.logger.exception("Unexpected error in chat endpoint")
        return jsonify(error=f"Wystąpił nieoczekiwany błąd: {str(exc)}"), 500

    return jsonify(reply=reply)
