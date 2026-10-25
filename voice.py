import time

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
)


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
