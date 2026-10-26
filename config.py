MODEL = "qwen3:8b"

APP_ALIASES = {
    "vs code": "visual studio code",
    "vscode": "visual studio code",
    "chrome": "google chrome",
    "edge": "microsoft edge",
    "spotify app": "spotify",
    "steam launcher": "steam",
    "epic": "epic games launcher",
    "fn": "fortnite",
}

SAMPLE_RATE = 16000
WAKE_WORD_MODEL = "hey_jarvis"
WAKE_WORD_THRESHOLD = 0.5
CHUNK_SECONDS = 0.2
END_SILENCE_SECONDS = 0.8
ENERGY_THRESHOLD = 350
START_TIMEOUT_SECONDS = 8
CONVERSATION_IDLE_TIMEOUT_SECONDS = 20
MAX_SPEECH_SECONDS = 12
SPEECH_LANGUAGE = "en-IN"

FUZZY_MATCH_CUTOFF = 0.55
SUGGESTION_MATCH_CUTOFF = 0.35
MAX_PARTIAL_SUGGESTIONS = 5
MAX_FUZZY_SUGGESTIONS = 3
