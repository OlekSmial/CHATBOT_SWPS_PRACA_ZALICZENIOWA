from flask import Blueprint, jsonify, request
import requests

BASE_URL = "https://api.openalex.org"

openalex_bp = Blueprint('openalex', __name__)

@openalex_bp.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    url = f"{BASE_URL}/works"
    params = {"search": query, "per_page": 10}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch data from OpenAlex"}), 500

    return jsonify(response.json())


# dodałem nowe api OpenAlex, api działa poprawnie w terminalu zwraca wartość, niestety nie jest one zintegrowane z moim chatem. Przejrzyj wszystkie pliki projketu i powiedz mi co zmienić aby chat korzystał tez z tego api OpenAlex. Chciałbym aby chat korzystał z tego api w momencie kiedy użytkownik zada pytanie związane z nauką, badaniami, publikacjami itp a nie moze znaleść informacji w bazie swps. Wtedy chat powinien automatycznie wysłać zapytanie do api OpenAlex i zwrócić odpowiedź użytkownikowi.

