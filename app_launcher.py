import os
import re
import subprocess
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import (
    APP_ALIASES,
    FUZZY_MATCH_CUTOFF,
    MAX_FUZZY_SUGGESTIONS,
    MAX_PARTIAL_SUGGESTIONS,
    SUGGESTION_MATCH_CUTOFF,
)


def normalize_name(name: str) -> str:
    """Convert an application name into a consistent comparison format."""
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def discover_app_shortcuts() -> Dict[str, Path]:
    """Recursively discover Windows Start Menu shortcuts."""
    folders = [
        Path.home()
        / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        / "Microsoft/Windows/Start Menu/Programs",
    ]

    app_paths: Dict[str, Path] = {}
    for folder in folders:
        if not folder.is_dir():
            continue

        for shortcut in folder.rglob("*.lnk"):
            app_name = normalize_name(shortcut.stem)
            if app_name and app_name not in app_paths:
                app_paths[app_name] = shortcut

    return app_paths


# Discover shortcuts once when LARVA starts.
APP_PATHS = discover_app_shortcuts()


def find_app(app_name: str) -> Tuple[Optional[Path], List[str]]:
    query = normalize_name(app_name)
    query = APP_ALIASES.get(query, query)

    if not query:
        return None, []

    if query in APP_PATHS:
        return APP_PATHS[query], []

    partial_matches = [name for name in APP_PATHS if query in name]

    if len(partial_matches) == 1:
        name = partial_matches[0]
        words = name.split()
        if len(words) > 1 and query == words[0]:
            return None, [APP_PATHS[name].stem]
        return APP_PATHS[name], []

    if len(partial_matches) > 1:
        suggestions = [
            APP_PATHS[name].stem
            for name in partial_matches[:MAX_PARTIAL_SUGGESTIONS]
        ]
        return None, suggestions

    matches = get_close_matches(
        query,
        list(APP_PATHS),
        n=1,
        cutoff=FUZZY_MATCH_CUTOFF,
    )
    if matches:
        return None, [APP_PATHS[matches[0]].stem]

    suggestions = get_close_matches(
        query,
        list(APP_PATHS),
        n=MAX_FUZZY_SUGGESTIONS,
        cutoff=SUGGESTION_MATCH_CUTOFF,
    )
    return None, [APP_PATHS[name].stem for name in suggestions]


def open_application(app_name: str) -> str:
    """Open a Windows application or request confirmation for suggestions."""
    query = normalize_name(app_name)
    query = APP_ALIASES.get(query, query)

    executable_aliases = {
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "notepad": "notepad.exe",
        "paint": "mspaint.exe",
        "mspaint": "mspaint.exe",
        "cmd": "cmd.exe",
        "command prompt": "cmd.exe",
    }

    if query in executable_aliases:
        try:
            subprocess.Popen(executable_aliases[query])
            return f"Successfully opened {app_name}."
        except OSError as error:
            return f"Could not open {app_name}: {error}"

    shortcut, suggestions = find_app(app_name)
    if shortcut is None:
        if not suggestions:
            return f"Couldn't find '{app_name}'."

        print("\nPossible matches:")
        for number, suggestion in enumerate(suggestions, start=1):
            print(f"{number}. {suggestion}")

        choice = input("Choose a number, or press Enter to cancel: ").strip()
        if not choice:
            return "Opening cancelled."
        if not choice.isdigit():
            return "Invalid selection."

        selected_number = int(choice)
        if selected_number < 1 or selected_number > len(suggestions):
            return "Invalid selection."

        selected_name = normalize_name(suggestions[selected_number - 1])
        shortcut = APP_PATHS.get(selected_name)
        if shortcut is None:
            return "Could not resolve the selected application."

    try:
        os.startfile(str(shortcut))
        return f"Successfully opened {shortcut.stem}."
    except OSError as error:
        return f"Found {shortcut.stem}, but couldn't open it: {error}"


def detect_open_command(user_input: str) -> Optional[str]:
    """Extract an application name from a direct open/launch/start command."""
    text = user_input.strip()
    text = re.sub(
        r"^(?:hi|hello|hey)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^(?:hey\s+)?larva[\s,:]+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    prefixes = ("could you ", "can you ", "would you ", "please ")
    while True:
        for prefix in prefixes:
            if text.lower().startswith(prefix):
                text = text[len(prefix):].strip()
                break
        else:
            break

    match = re.match(
        r"^(?:open|launch|start)\s+(?:the\s+)?"
        r"(.+?)(?:\s+please)?[.!?]*$",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(" \"'")
    return None
