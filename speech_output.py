from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue
import tempfile
from threading import Event, Lock, Thread
from typing import Any, Optional
import wave


@dataclass
class _SpeechRequest:
    text: str
    completed: Event = field(default_factory=Event)
    error: Optional[str] = None


_requests: Queue[_SpeechRequest] = Queue()
_worker_lock = Lock()
_worker_started = False


def _create_engine() -> Any:
    import pyttsx3

    engine = pyttsx3.init("sapi5")
    engine.setProperty("rate", 175)
    engine.setProperty("volume", 0.9)
    return engine


def _play_buffered_wav(engine: Any, text: str) -> None:
    import winsound

    with tempfile.TemporaryDirectory(prefix="larva_tts_") as temporary_directory:
        source_path = Path(temporary_directory) / "speech.wav"
        buffered_path = Path(temporary_directory) / "speech_buffered.wav"

        engine.save_to_file(text, str(source_path))
        engine.runAndWait()

        if not source_path.is_file() or source_path.stat().st_size == 0:
            raise OSError("SAPI5 did not create the synthesized WAV file.")

        with wave.open(str(source_path), "rb") as source:
            parameters = source.getparams()
            audio_frames = source.readframes(parameters.nframes)

        if not audio_frames:
            raise OSError("SAPI5 created a WAV file without audio frames.")

        if parameters.comptype != "NONE":
            raise wave.Error(
                f"Unsupported synthesized WAV compression: "
                f"{parameters.comptype}"
            )

        silence_frame_count = round(parameters.framerate * 0.25)
        silence_sample_count = (
            silence_frame_count * parameters.nchannels * parameters.sampwidth
        )
        silence_value = b"\x80" if parameters.sampwidth == 1 else b"\x00"
        silence_frames = silence_value * silence_sample_count

        with wave.open(str(buffered_path), "wb") as buffered:
            buffered.setparams(parameters)
            buffered.writeframes(silence_frames + audio_frames)

        winsound.PlaySound(
            str(buffered_path),
            winsound.SND_FILENAME,
        )


def _speech_worker() -> None:
    engine = None

    while True:
        request = _requests.get()
        try:
            if engine is None:
                try:
                    engine = _create_engine()
                except Exception as error:
                    request.error = f"Could not initialize SAPI5: {error}"

            if engine is not None:
                try:
                    _play_buffered_wav(engine, request.text)
                except Exception as error:
                    request.error = f"SAPI5 synthesis or playback failed: {error}"
                    try:
                        engine.stop()
                    except Exception as cleanup_error:
                        print(
                            "Speech engine reset failed: "
                            f"{cleanup_error}"
                        )
                    engine = None
        finally:
            request.completed.set()
            _requests.task_done()


def _start_worker() -> None:
    global _worker_started

    with _worker_lock:
        if _worker_started:
            return

        worker = Thread(
            target=_speech_worker,
            name="LARVA-SAPI5",
            daemon=True,
        )
        worker.start()
        _worker_started = True


def speak(text: str) -> None:
    """Speak one complete text utterance offline using Windows SAPI5."""
    if not text or not text.strip():
        return

    request = _SpeechRequest(text=text.strip())
    _start_worker()
    _requests.put(request)
    request.completed.wait()

    if request.error:
        print(f"Speech output failed: {request.error}")
