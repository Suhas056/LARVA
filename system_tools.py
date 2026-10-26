import re
from datetime import datetime
from pathlib import Path
from typing import Optional


_SCREENSHOT_REQUEST = re.compile(
    r"(?:(?:please|kindly)\s+)?"
    r"(?:(?:can|could|would)\s+you\s+)?"
    r"(?:(?:please|kindly)\s+)?"
    r"(?:"
    r"(?:take|capture|grab|save)\s+"
    r"(?:(?:a|the|my)\s+)?"
    r"(?:screenshot|screen\s+shot|screen\s+capture|screen\s+grab)"
    r"(?:\s+of\s+(?:(?:my|the)\s+)?(?:screen|desktop))?"
    r"|(?:capture|grab)\s+(?:(?:my|the|a)\s+)?(?:screen|desktop)"
    r"|(?:take\s+)?(?:a|the|my)?\s*"
    r"(?:screenshot|screen\s+shot)\s+"
    r"(?:of\s+)?(?:my|the)\s+(?:screen|desktop)"
    r"|screenshot"
    r")"
    r"(?:\s+please)?[.!?]*",
    re.IGNORECASE,
)


def detect_screenshot_command(user_input: str) -> bool:
    """Return whether the entire input is an explicit screenshot request."""
    text = re.sub(r"\s+", " ", user_input.strip())
    text = re.sub(
        r"^(?:(?:hey\s+)?(?:larva|jarvis)[,:]?\s+)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return _SCREENSHOT_REQUEST.fullmatch(text) is not None


def take_screenshot() -> str:
    """Capture the Windows desktop and save a unique PNG in the user's Pictures."""
    screenshot_path: Optional[Path] = None
    screenshot_file_created = False
    try:
        from PIL import ImageGrab

        screenshot_directory = (
            Path.home() / "Pictures" / "LARVA Screenshots"
        )
        screenshot_directory.mkdir(parents=True, exist_ok=True)

        image = ImageGrab.grab()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"larva_screenshot_{timestamp}.png"
        screenshot_path = screenshot_directory / filename
        suffix = 1
        while True:
            try:
                screenshot_file = screenshot_path.open("xb")
                screenshot_file_created = True
                break
            except FileExistsError:
                screenshot_path = screenshot_directory / (
                    f"larva_screenshot_{timestamp}_{suffix}.png"
                )
                suffix += 1

        with screenshot_file:
            image.save(screenshot_file, format="PNG")

        if screenshot_path.stat().st_size == 0:
            raise OSError("The saved screenshot file is empty.")

        return str(screenshot_path.resolve())
    except Exception as error:
        cleanup_message = ""
        if (
            screenshot_file_created
            and screenshot_path is not None
            and screenshot_path.exists()
        ):
            try:
                screenshot_path.unlink()
            except OSError as cleanup_error:
                cleanup_message = f" Partial file cleanup failed: {cleanup_error}"
        return f"Screenshot failed: {error}.{cleanup_message}"
