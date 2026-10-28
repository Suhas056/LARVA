import ipaddress
import os
import re
import shutil
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


WEBSITE_ALIASES = {
    "linkedin": "https://www.linkedin.com/",
    "youtube": "https://www.youtube.com/",
    "google": "https://www.google.com/",
    "github": "https://github.com/",
    "chatgpt": "https://chatgpt.com/",
    "gmail": "https://mail.google.com/",
    "instagram": "https://www.instagram.com/",
    "spotify": "https://open.spotify.com/",
    "reddit": "https://www.reddit.com/",
    "stack overflow": "https://stackoverflow.com/",
}

_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_DOMAIN_LABEL_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)


def _is_valid_hostname(hostname: str) -> bool:
    if not hostname or len(hostname) > 253:
        return False

    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass

    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return False

    labels = ascii_hostname.rstrip(".").split(".")
    return bool(labels) and all(
        _DOMAIN_LABEL_PATTERN.fullmatch(label) for label in labels
    )


def _resolve_website_url(website: str) -> str:
    if not isinstance(website, str):
        raise ValueError("Website must be provided as text.")

    value = website.strip()
    if not value:
        raise ValueError("Website cannot be empty.")

    alias = WEBSITE_ALIASES.get(value.casefold())
    if alias:
        return alias

    if any(character.isspace() for character in value):
        raise ValueError("Website must be a URL, domain, or supported site name.")

    if _SCHEME_PATTERN.match(value):
        parsed = urlsplit(value)
        if parsed.scheme.casefold() not in {"http", "https"}:
            raise ValueError("Only HTTP and HTTPS websites are supported.")
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("The HTTP or HTTPS URL is malformed.")
        if not parsed.netloc or not parsed.hostname:
            raise ValueError("The HTTP or HTTPS URL must include a hostname.")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URLs containing user credentials are not allowed.")
        if not _is_valid_hostname(parsed.hostname):
            raise ValueError("The URL contains an invalid hostname.")
        try:
            parsed.port
        except ValueError as error:
            raise ValueError("The URL contains an invalid port.") from error
        return urlunsplit(parsed)

    parsed = urlsplit(f"//{value}")
    if not parsed.netloc or not parsed.hostname:
        raise ValueError("Enter a valid website domain or HTTP/HTTPS URL.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Website domains cannot contain user credentials.")
    if not _is_valid_hostname(parsed.hostname):
        raise ValueError("Enter a valid website domain.")
    try:
        parsed.port
    except ValueError as error:
        raise ValueError("The website contains an invalid port.") from error

    return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def is_website_target(target: str) -> bool:
    """Return whether text looks like a URL or domain target."""
    if not isinstance(target, str):
        return False
    value = target.strip()
    if not value:
        return False
    if _SCHEME_PATTERN.match(value):
        return True
    return not any(character.isspace() for character in value) and "." in value


def detect_website_request(
    user_input: str,
) -> tuple[str, str | None] | None:
    """Extract only explicit website requests; app names remain the default."""
    text = user_input.strip()
    text = re.sub(r"[.!?]+$", "", text).strip()

    explicit_patterns = (
        (
            r"^(?:please\s+)?(?:open|launch|visit)\s+(.+?)\s+"
            r"in\s+(?:google\s+)?chrome$",
            "chrome",
        ),
        (
            r"^(?:please\s+)?(?:open|launch)\s+(.+?)\s+"
            r"in\s+(?:(?:my|the|a)\s+)?browser$",
            None,
        ),
        (
            r"^(?:please\s+)?(?:open|launch)\s+(.+?)\s+"
            r"(?:website|site)$",
            None,
        ),
        (r"^(?:please\s+)?visit\s+(.+)$", None),
    )
    for pattern, browser in explicit_patterns:
        match = re.fullmatch(pattern, text, flags=re.IGNORECASE)
        if match:
            target = match.group(1).strip()
            if target:
                return target, browser

    match = re.fullmatch(
        r"^(?:please\s+)?(?:open|launch)\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    target = match.group(1).strip() if match else text
    if target and is_website_target(target):
        return target, None
    return None


def _chrome_executable_from_registry() -> Path | None:
    if os.name != "nt":
        return None

    try:
        import winreg
    except ImportError:
        return None

    registry_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
    registry_locations = (
        (winreg.HKEY_CURRENT_USER, 0),
        (winreg.HKEY_LOCAL_MACHINE, 0),
        (winreg.HKEY_LOCAL_MACHINE, getattr(winreg, "KEY_WOW64_32KEY", 0)),
    )
    for root, view_flag in registry_locations:
        try:
            with winreg.OpenKey(root, registry_key, 0, winreg.KEY_READ | view_flag) as key:
                executable, _value_type = winreg.QueryValueEx(key, None)
            candidate = Path(os.path.expandvars(executable.strip('"')))
            if candidate.is_file():
                return candidate
        except (OSError, TypeError, ValueError):
            continue

    return None


def _find_chrome_executable() -> Path | None:
    candidates: list[Path] = []

    for command in ("chrome", "chrome.exe"):
        executable = shutil.which(command)
        if executable:
            candidates.append(Path(executable))

    installation_roots = (
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
        r"C:\Program Files",
        r"C:\Program Files (x86)",
    )
    for root in installation_roots:
        if root:
            candidates.append(
                Path(root)
                / "Google"
                / "Chrome"
                / "Application"
                / "chrome.exe"
            )

    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue

    return _chrome_executable_from_registry()


def open_website(website: str, browser: str | None = None) -> str:
    """Open a validated HTTP(S) website in the requested browser."""
    try:
        url = _resolve_website_url(website)
    except ValueError as error:
        return f"Website request rejected: {error}"

    try:
        if browser is None or browser.strip().casefold() in {
            "default",
            "browser",
            "my browser",
            "the browser",
        }:
            opened = webbrowser.open_new_tab(url)
            browser_name = "default browser"
        elif browser.strip().casefold() in {"chrome", "google chrome"}:
            executable = _find_chrome_executable()
            if executable is None:
                return (
                    "Could not open website in Google Chrome: "
                    "Chrome could not be located. Install Chrome or add "
                    "chrome.exe to PATH."
                )
            controller = webbrowser.BackgroundBrowser(str(executable))
            opened = controller.open_new_tab(url)
            browser_name = "Google Chrome"
        else:
            return f"Website request rejected: unsupported browser '{browser}'."

        if opened:
            return f"Opened {url} in {browser_name}."
        return f"Could not open {url} in {browser_name}."
    except Exception as error:
        selected_browser = browser or "default browser"
        return f"Could not open {url} in {selected_browser}: {error}"
