import time
from typing import Any, Optional

import numpy as np
import sounddevice as sd
import speech_recognition as sr

from config import (
    CHUNK_SECONDS,
    END_SILENCE_SECONDS,
    ENERGY_THRESHOLD,
    MAX_SPEECH_SECONDS,
    SAMPLE_RATE,
    SPEECH_LANGUAGE,
    START_TIMEOUT_SECONDS,
    WAKE_WORD_MODEL,
    WAKE_WORD_THRESHOLD,
)

WAKE_WORD_FRAME_SAMPLES = 1280
WAKE_WORD_RELEASE_SILENCE_FRAMES = 3
WAKE_WORD_RELEASE_TIMEOUT_SECONDS = 2.0

_wake_word_detector: Optional[Any] = None
_wake_word_model_key: Optional[str] = None


def _get_wake_word_detector() -> tuple[Any, str]:
    global _wake_word_detector, _wake_word_model_key

    if _wake_word_detector is None:
        from openwakeword.model import Model

        detector = Model(
            wakeword_models=[WAKE_WORD_MODEL],
            inference_framework="onnx",
        )
        model_key = next(
            (
                key
                for key in detector.models
                if "jarvis" in key.lower()
            ),
            None,
        )
        if model_key is None:
            raise RuntimeError(
                f"Loaded wake-word model '{WAKE_WORD_MODEL}' was not found."
            )

        _wake_word_detector = detector
        _wake_word_model_key = model_key

    if _wake_word_model_key is None:
        raise RuntimeError("The wake-word model was not initialized.")

    return _wake_word_detector, _wake_word_model_key


def wait_for_wake_word() -> bool:
    """Wait for Hey Jarvis; return False if the detector or microphone fails."""
    try:
        detector, model_key = _get_wake_word_detector()
        detector.reset()

        print("\nWaiting for 'Hey Jarvis'...")
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=WAKE_WORD_FRAME_SAMPLES,
        ) as microphone:
            while True:
                audio_chunk, _ = microphone.read(
                    WAKE_WORD_FRAME_SAMPLES
                )
                frame = np.squeeze(audio_chunk)
                scores = detector.predict(frame)
                score = float(scores.get(model_key, 0.0))

                if score < WAKE_WORD_THRESHOLD:
                    continue

                detector.reset()
                print(f"\nWake word detected (score: {score:.3f}).")

                silence_frames = 0
                release_started_at = time.monotonic()
                while silence_frames < WAKE_WORD_RELEASE_SILENCE_FRAMES:
                    if (
                        time.monotonic() - release_started_at
                        >= WAKE_WORD_RELEASE_TIMEOUT_SECONDS
                    ):
                        print(
                            "Audio remained active after the wake word; "
                            "continuing to command listening."
                        )
                        break

                    trailing_audio, _ = microphone.read(
                        WAKE_WORD_FRAME_SAMPLES
                    )
                    volume = float(
                        np.sqrt(
                            np.mean(
                                trailing_audio.astype(np.float32) ** 2
                            )
                        )
                    )
                    if volume < ENERGY_THRESHOLD:
                        silence_frames += 1
                    else:
                        silence_frames = 0

                detector.reset()
                return True

    except KeyboardInterrupt:
        print("\nWake-word listening stopped.")
        return False
    except Exception as error:
        print(f"\nWake-word or microphone error: {error}")
        return False

def listen_for_command() -> str:
    chunk_frames = int(SAMPLE_RATE * CHUNK_SECONDS)
    silence_chunks_needed = int(END_SILENCE_SECONDS / CHUNK_SECONDS)

    recognizer = sr.Recognizer()
    audio_chunks = []
    speech_started_at = None
    silence_chunks = 0
    wait_started_at = time.monotonic()

    try:
        print("\nLARVA is listening... speak now!")

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=chunk_frames,
        ) as stream:
            while True:
                now = time.monotonic()
                if speech_started_at is None:
                    if now - wait_started_at >= START_TIMEOUT_SECONDS:
                        print("No speech detected. Try again.")
                        return ""
                elif now - speech_started_at >= MAX_SPEECH_SECONDS:
                    break

                recording, _overflowed = stream.read(chunk_frames)
                volume = float(
                    np.sqrt(
                        np.mean(recording.astype(np.float32) ** 2)
                    )
                )

                if speech_started_at is None:
                    if volume >= ENERGY_THRESHOLD:
                        speech_started_at = time.monotonic()
                        audio_chunks.append(recording.copy())
                        print(
                            "Speech detected. "
                            "Pause when you're finished."
                        )
                    continue

                audio_chunks.append(recording.copy())
                if volume < ENERGY_THRESHOLD:
                    silence_chunks += 1
                else:
                    silence_chunks = 0

                if silence_chunks >= silence_chunks_needed:
                    break

        if not audio_chunks:
            return ""

        print("Converting speech to text...")
        recording = np.concatenate(audio_chunks, axis=0)
        audio = sr.AudioData(recording.tobytes(), SAMPLE_RATE, 2)
        text = recognizer.recognize_google(
            audio,
            language=SPEECH_LANGUAGE,
        )

        print(f"You said: {text}")
        return text.strip()

    except sr.UnknownValueError:
        print("LARVA couldn't understand. Try again.")
        return ""
    except sr.RequestError as error:
        print(f"Speech recognition service error: {error}")
        return ""
    except Exception as error:
        print(f"Microphone or recording error: {error}")
        return ""
