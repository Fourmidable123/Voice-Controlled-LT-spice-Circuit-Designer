import os
import time

import speech_recognition as sr
from pydub import AudioSegment

from vclt.config import CIRCUIT_DIR
from vclt.ltspice import open_in_ltspice
from vclt.parser import parse_command
from vclt.schematic import generate_circuit_schematic


def _save_schematic(components):
    schematic_content = generate_circuit_schematic(components)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    circuit_filename = f"circuit_{timestamp}.asc"
    circuit_path = os.path.join(CIRCUIT_DIR, circuit_filename)
    with open(circuit_path, "w") as file_obj:
        file_obj.write(schematic_content)
    return circuit_filename, circuit_path


def process_text(text):
    if not text or not text.strip():
        return "Please enter a circuit description first."

    try:
        components = parse_command(text)
        topology = components.get("topology", "basic_circuit")
        circuit_filename, circuit_path = _save_schematic(components)
        _, message = open_in_ltspice(circuit_path)
        return (
            "Circuit created successfully!\\n"
            f"Recognized: {text}\\n"
            f"Topology: {topology}\\n"
            f"Components: {components}\\n"
            f"Saved as: {circuit_filename}\\n"
            f"{message}"
        )
    except Exception as exc:
        return f"Error: {exc}"


def process_audio(audio_path):
    recognizer = sr.Recognizer()
    temp_files = []

    try:
        audio = AudioSegment.from_file(audio_path)
        wav_path = os.path.join(CIRCUIT_DIR, "temp.wav")
        audio.export(wav_path, format="wav")
        temp_files.append(wav_path)

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            try:
                command = recognizer.recognize_google(audio_data)
                components = parse_command(command)
                circuit_filename, circuit_path = _save_schematic(components)
                _, message = open_in_ltspice(circuit_path)
                return (
                    "Circuit created successfully!\\n"
                    f"Recognized: {command}\\n"
                    f"Components: {components}\\n"
                    f"Saved as: {circuit_filename}\\n"
                    f"{message}"
                )
            except sr.UnknownValueError:
                return "Could not understand audio"
            except sr.RequestError:
                return "Speech recognition service error"
            except Exception as exc:
                return f"Error: {exc}"
    finally:
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass


def preview_command(text):
    if not text or not text.strip():
        return "### Parser Preview\\nEnter text in the Text Input tab to preview extracted values."
    components = parse_command(text)
    topology = components.get("topology", "basic_circuit")
    return (
        "### Parser Preview\\n"
        f"- Input: `{text}`\\n"
        f"- Topology: `{topology}`\\n"
        f"- Extracted Components: `{components}`"
    )


def list_recent_circuits(limit=8):
    try:
        asc_files = [
            os.path.join(CIRCUIT_DIR, name)
            for name in os.listdir(CIRCUIT_DIR)
            if name.lower().endswith(".asc")
        ]
        asc_files.sort(key=os.path.getmtime, reverse=True)
        if not asc_files:
            return "No generated circuit files yet."
        return "\\n".join(os.path.basename(path) for path in asc_files[:limit])
    except Exception as exc:
        return f"Could not list circuit files: {exc}"
