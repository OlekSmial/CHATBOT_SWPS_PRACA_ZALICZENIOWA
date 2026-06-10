from flask import Blueprint, jsonify, request
import requests

openalex_bp = Blueprint('openalex', __name__)

BASE_URL = "https://api.openalex.org"

@openalex_bp.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    response = requests.get(f"{BASE_URL}/works", params={"search": query, "per_page": 10})
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch data from OpenAlex"}), 500

    return jsonify(response.json())