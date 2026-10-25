import sounddevice as sd
import speech_recognition as sr

SAMPLE_RATE = 16000
DURATION = 5

recognizer = sr.Recognizer()

try:
    print("Speak now! Recording for 5 seconds...")

    recording = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16"
    )

    sd.wait()

    print("Converting speech to text...")

    audio = sr.AudioData(
        recording.tobytes(),
        SAMPLE_RATE,
        2
    )

    text = recognizer.recognize_google(
        audio,
        language="en-IN"
    )

    print("You said:", text)

except sr.UnknownValueError:
    print("I couldn't understand the speech. Try again.")

except sr.RequestError as error:
    print("Speech recognition service error:", error)

except Exception as error:
    print("Microphone or recording error:", error)