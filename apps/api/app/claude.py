"""Cienka warstwa pośrednia nad API Anthropic Claude dla endpointu czatu."""

import os

import anthropic

from app.knowledge import MAIN_KNOWLEDGE
from app.repository import search_as_text as swps_search
from app.openalex import search_as_text as openalex_search

MODEL = "claude-opus-4-8"
MAX_TOKENS = 2048
# Zabezpieczenie przed nieskończoną pętlą wywołań narzędzia.
MAX_TOOL_ITERS = 4


def _env_flag(name: str, default: bool = True) -> bool:
    """Czyta flagę typu prawda/fałsz ze zmiennej środowiskowej."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on", "tak")


# Włącznik RAG: gdy False, wyszukiwanie w repozytorium SWPS jest wyłączone —
# narzędzie nie jest przekazywane modelowi, a prompt o nim nie wspomina.
# Sterowane zmienną RAG_ENABLED w pliku .env (domyślnie włączone).
RAG_ENABLED = _env_flag("RAG_ENABLED", True)

# Część wspólna instrukcji (niezależna od RAG).
_INSTRUCTIONS_BASE = (
    "Jesteś 'Asystentem Laika' – przyjaznym chatbotem stworzonym dla studentów i pasjonatów, "
    "którzy gubią się w trudnym żargonie naukowym. Twoim zadaniem jest tłumaczenie "
    "skomplikowanych pojęć akademickich i badań psychologicznych na prosty, potoczny język. "
    "Zawsze odpowiadaj po polsku. Używaj życiowych analogii, unikaj trudnych słów (albo od razu je wyjaśniaj). "
    "Bądź empatyczny, cierpliwy i bezpośredni. Odpowiadaj konkretnie, bez zbędnych meta-komentarzy "
    "czy opisywania swojego procesu myślowego. Jeśli masz dostęp do bazy wiedzy poniżej, korzystaj z niej."
)

# Dodatek instrukcji aktywny tylko, gdy RAG jest włączony.
_INSTRUCTIONS_RAG = (
    "Jeśli użytkownik pyta o badania, publikacje, artykuły lub naukowców z SWPS, "
    "ZAWSZE najpierw wywołaj narzędzie `szukaj_w_repozytorium`. "
    "Jeśli pytanie dotyczy tematów spoza SWPS lub repozytorium nie zwróciło wyników, "
    "wywołaj narzędzie `szukaj_w_openalex`, które przeszukuje globalną bazę publikacji naukowych. "
    "Po otrzymaniu wyników NIE CYTUJ dosłownie suchych abstraktów. Zamiast tego opowiedz "
    "o znalezionych badaniach własnymi, prostymi słowami – tak, jakbyś opowiadał o nich "
    "znajomemu przy kawie. Wyjaśnij, co z tych badań wynika dla przeciętnego człowieka. "
    "Na koniec swojej wypowiedzi zawsze podaj linki do źródeł, żeby użytkownik mógł sprawdzić szczegóły."
)

_INSTRUCTIONS_TAIL = (
    "Jeśli nie potrafisz znaleźć odpowiedzi na zadane pytanie ani w repozytorium, "
    "ani w ogólnej wiedzy, po prostu przyznaj się do tego i powiedz to wprost, bez wymyślania."
)

_INSTRUCTIONS = _INSTRUCTIONS_BASE + (_INSTRUCTIONS_RAG if RAG_ENABLED else "") + _INSTRUCTIONS_TAIL

# Narzędzia udostępniane modelowi: wyszukiwanie w SWPS i OpenAlex na żądanie.
# Stabilne między zapytaniami, więc nie psują prompt cache.
_TOOLS = [
    {
        "name": "szukaj_w_repozytorium",
        "description": (
            "Przeszukuje repozytorium naukowe SWPS (DSpace) i zwraca pasujące "
            "publikacje: tytuł, autorów, rok, słowa kluczowe, abstrakt i link. "
            "Wywołaj, gdy pytanie dotyczy publikacji, badań, autorów lub tematów "
            "naukowych SWPS — zanim udzielisz odpowiedzi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zapytanie": {
                    "type": "string",
                    "description": "Słowa kluczowe do wyszukania (temat, autor, tytuł).",
                }
            },
            "required": ["zapytanie"],
        },
    },
    {
        "name": "szukaj_w_openalex",
        "description": (
            "Przeszukuje globalną bazę OpenAlex zawierającą setki milionów publikacji "
            "naukowych z całego świata. Zwraca tytuł, autorów, rok, abstrakt i link. "
            "Wywołaj gdy pytanie dotyczy tematów spoza SWPS, ogólnych zagadnień naukowych "
            "lub gdy repozytorium SWPS nie zwróciło wyników."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zapytanie": {
                    "type": "string",
                    "description": "Słowa kluczowe do wyszukania po polsku lub angielsku.",
                }
            },
            "required": ["zapytanie"],
        },
    },
]


def _build_system_prompt() -> list[dict]:
    """Instrukcje + główna baza wiedzy jako stabilny, buforowany blok promptu.

    Treść jest identyczna bajt po bajcie między zapytaniami, dzięki czemu
    prefiks może być buforowany (prompt caching). Wiedza szczegółowa nie jest
    tu wstawiana — model doczytuje ją na żądanie narzędziem wyszukiwania.
    """
    text = _INSTRUCTIONS
    if MAIN_KNOWLEDGE:
        text += f"\n\n# Baza wiedzy\n\n{MAIN_KNOWLEDGE}"
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


SYSTEM_PROMPT = _build_system_prompt()

# Jeden współdzielony klient dla wszystkich zapytań. Czyta ANTHROPIC_API_KEY ze środowiska.
_client = anthropic.Anthropic()


def generate_reply(message: str, history: list[dict] | None = None) -> str:
    """Wysyła rozmowę do Claude i zwraca tekst odpowiedzi asystenta.

    Obsługuje pętlę wywołań narzędzia: jeśli model poprosi o wyszukanie w
    repozytorium lub OpenAlex, wykonujemy je i zwracamy wynik, aż model udzieli
    ostatecznej odpowiedzi. Gdy RAG jest wyłączony (RAG_ENABLED=False), pomijamy
    narzędzia i wykonujemy zwykłe pojedyncze zapytanie. `history` to opcjonalna
    lista wcześniejszych tur jako słowniki {"role", "content"}.
    """
    messages = _build_messages(message, history)

    # RAG wyłączony — zwykły czat bez narzędzi wyszukiwania.
    if not RAG_ENABLED:
        response = _client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT, messages=messages
        )
        return _text(response)

    for _ in range(MAX_TOOL_ITERS):
        response = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=_TOOLS,
        )

        if response.stop_reason != "tool_use":
            return _text(response)

        # Wykonaj żądane wyszukiwania i dołącz wyniki jako tool_result.
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            query = (block.input or {}).get("zapytanie", "")
            if block.name == "szukaj_w_repozytorium":
                content = swps_search(query)
            elif block.name == "szukaj_w_openalex":
                content = openalex_search(query)
            else:
                continue
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })
        messages.append({"role": "user", "content": tool_results})

    # Limit iteracji wyczerpany — wymuś odpowiedź końcową bez narzędzi.
    final = _client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT, messages=messages
    )
    return _text(final)


def _text(response) -> str:
    """Skleja tekstowe bloki odpowiedzi w jeden ciąg."""
    return "".join(block.text for block in response.content if block.type == "text")


def _build_messages(message: str, history: list[dict] | None) -> list[dict]:
    """Normalizuje historię do poprawnej tablicy wiadomości Anthropic.

    Pomija wszystko, co nie jest turą user/assistant, oraz usuwa początkowe
    tury asystenta (pierwsza wiadomość musi pochodzić od użytkownika).
    """
    messages: list[dict] = []
    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        if not messages and role != "user":
            continue  # pomiń początkowe tury asystenta (np. wstępne powitanie)
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})
    return messages