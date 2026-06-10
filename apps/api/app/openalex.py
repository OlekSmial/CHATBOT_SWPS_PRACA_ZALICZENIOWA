from flask import Blueprint, jsonify, request
import requests

BASE_URL = "https://api.openalex.org"
openalex_bp = Blueprint('openalex', __name__)


@openalex_bp.route('/search', methods=['GET'])
def search_endpoint():
    query = request.args.get('query', '')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    try:
        results = search(query)
        return jsonify(results)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def search(query: str, per_page: int = 5) -> list[dict]:
    """Wyszukuje prace w OpenAlex i zwraca uproszczone rekordy."""
    params = {
        "search": query,
        "per_page": per_page,
        "select": "id,title,authorships,publication_year,abstract_inverted_index,primary_location,open_access",
    }
    response = requests.get(f"{BASE_URL}/works", params=params, timeout=10)
    response.raise_for_status()

    results = []
    for work in response.json().get("results", []):
        authors = [
            a["author"]["display_name"]
            for a in work.get("authorships", [])[:6]
            if a.get("author", {}).get("display_name")
        ]
        location = work.get("primary_location") or {}
        source = location.get("source") or {}
        url = (
            (work.get("open_access") or {}).get("oa_url")
            or location.get("landing_page_url")
            or work.get("id", "")
        )
        results.append({
            "title": work.get("title", ""),
            "authors": authors,
            "year": str(work.get("publication_year", "")),
            "abstract": _decode_abstract(work.get("abstract_inverted_index"))[:600],
            "journal": source.get("display_name", ""),
            "url": url,
        })
    return results


def _decode_abstract(inverted_index: dict | None) -> str:
    """Zamienia odwrócony indeks OpenAlex na zwykły tekst."""
    if not inverted_index:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words))


def search_as_text(query: str, per_page: int = 5) -> str:
    """Formatuje wyniki jako tekst gotowy do przekazania modelowi."""
    try:
        results = search(query, per_page)
    except Exception as exc:
        return f"(Błąd wyszukiwania w OpenAlex: {exc})"
    if not results:
        return f'(Brak wyników w OpenAlex dla zapytania: "{query}".)'

    blocks = []
    for i, r in enumerate(results, 1):
        parts = [f"{i}. {r['title']}"]
        if r["authors"]:
            parts.append("Autorzy: " + ", ".join(r["authors"]))
        if r["year"]:
            parts.append("Rok: " + r["year"])
        if r["journal"]:
            parts.append("Źródło: " + r["journal"])
        if r["abstract"]:
            parts.append("Abstrakt: " + r["abstract"])
        if r["url"]:
            parts.append("Link: " + r["url"])
        blocks.append("\n".join(parts))
    return "\n\n".join(blocks)

