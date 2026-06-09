"""Cienka warstwa pośrednia nad API Google Gemini dla endpointu czatu."""

import os
from google import genai
from google.genai import types

from app.knowledge import MAIN_KNOWLEDGE
from app.repository import search_as_text

# Zmiana na darmowy, potężny model od Google (Gemini Pro)
MODEL = "gemini-2.5-pro"

def _env_flag(name: str, default: bool = True) -> bool:
    """Czyta flagę typu prawda/fałsz ze zmiennej środowiskowej."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on", "tak")


# Włącznik RAG
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

_INSTRUCTIONS_RAG = (
    "Jeśli użytkownik pyta o badania, publikacje, artykuły lub naukowców z SWPS, "
    "ZAWSZE najpierw wywołaj narzędzie `szukaj_w_repozytorium`. Po otrzymaniu wyników "
    "NIE CYTUJ dosłownie suchych abstraktów. Zamiast tego opowiedz o znalezionych badaniach "
    "własnymi, prostymi słowami – tak, jakbyś opowiadał o nich znajomemu przy kawie. "
    "Wyjaśnij, co z tych badań wynika dla przeciętnego człowieka. Na koniec swojej wypowiedzi "
    "zawsze podaj linki do źródeł, żeby użytkownik mógł sprawdzić szczegóły."
)

_INSTRUCTIONS_TAIL = (
    "Jeśli nie potrafisz znaleźć odpowiedzi na zadane pytanie ani w repozytorium, "
    "ani w ogólnej wiedzy, po prostu przyznaj się do tego i powiedz to wprost, bez wymyślania."
)

_INSTRUCTIONS = _INSTRUCTIONS_BASE + (_INSTRUCTIONS_RAG if RAG_ENABLED else "") + _INSTRUCTIONS_TAIL


def _build_system_instruction() -> str:
    """Buduje główny blok instrukcji (System Prompt)."""
    text = _INSTRUCTIONS
    if MAIN_KNOWLEDGE:
        text += f"\n\n# Baza wiedzy\n\n{MAIN_KNOWLEDGE}"
    return text

SYSTEM_INSTRUCTION = _build_system_instruction()

# Inicjalizacja klienta Google (Czyta GEMINI_API_KEY ze środowiska)
_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


# Narzędzie udostępniane modelowi (Gemini potrafi korzystać z funkcji Pythona bezpośrednio!)
def szukaj_w_repozytorium(zapytanie: str) -> str:
    """Przeszukuje repozytorium naukowe SWPS (DSpace) i zwraca pasujące publikacje: tytuł, autorów, rok, słowa kluczowe, abstrakt i link.
    Wywołaj, gdy pytanie dotyczy publikacji, badań, autorów lub tematów naukowych SWPS — zanim udzielisz odpowiedzi."""
    return search_as_text(zapytanie)


def generate_reply(message: str, history: list[dict] | None = None) -> str:
    """Wysyła rozmowę do Gemini i zwraca tekst odpowiedzi asystenta."""
    
    # 1. Konfiguracja modelu
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
    )
    
    # Jeśli RAG włączony, dajemy modelowi dostęp do narzędzia wyszukiwania w bazie SWPS
    if RAG_ENABLED:
        config.tools = [szukaj_w_repozytorium]

    # 2. Przygotowanie historii
    messages = _build_history(history)

    # 3. Utworzenie sesji czatu. Gemini automatycznie wykona narzędzia w tle, jeśli model o to poprosi!
    chat = _client.chats.create(
        model=MODEL,
        config=config,
        history=messages
    )

    # 4. Wysłanie wiadomości i pobranie odpowiedzi
    response = chat.send_message(message)
    return response.text


def _build_history(history: list[dict] | None) -> list[types.Content]:
    """Normalizuje historię do poprawnej tablicy wiadomości dla formatu Gemini."""
    contents = []
    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content")
        
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
            
        # Mapowanie ról na format Gemini (użytkownik = 'user', asystent = 'model')
        g_role = "user" if role == "user" else "model"
        
        # Ignorujemy pierwszą wiadomość, jeśli pochodzi od modelu (wymagane przez API)
        if not contents and g_role != "user":
            continue
            
        contents.append(
            types.Content(role=g_role, parts=[types.Part.from_text(text=content)])
        )

    return contents
