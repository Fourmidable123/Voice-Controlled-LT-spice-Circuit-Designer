import ast
import json
import os
import re

import google.generativeai as genai

from vclt.config import ALLOWED_COMPONENT_KEYS, SUPPORTED_TOPOLOGIES, logger

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()


def initialize_gemini_model():
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set. Falling back to rule-based parser.")
        return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        return genai.GenerativeModel("gemini-2.0-flash")
    except Exception as exc:
        logger.exception("Failed to initialize Gemini model: %s", exc)
        return None


MODEL = initialize_gemini_model()


def has_gemini_model():
    return MODEL is not None


def _extract_value(pattern, text, default=None):
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return default
    try:
        return float(match.group(1))
    except Exception:
        return default


def _parse_resistance(text, default=1.0):
    match = re.search(r"(\\d+(?:\\.\\d+)?)\\s*(meg|k|m)?\\s*(?:ohm|ohms|resistor)", text, flags=re.IGNORECASE)
    if not match:
        return default
    value = float(match.group(1))
    prefix = (match.group(2) or "").lower()
    multiplier = {"meg": 1e6, "k": 1e3, "m": 1e-3}.get(prefix, 1.0)
    return value * multiplier


def _parse_capacitance(text, default=100e-6):
    match = re.search(
        r"(\\d+(?:\\.\\d+)?)\\s*(micro|u|nano|n|pico|p|milli|m)?\\s*(?:f|farad|farads|capacitor)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return default
    value = float(match.group(1))
    prefix = (match.group(2) or "").lower()
    multiplier = {
        "milli": 1e-3,
        "m": 1e-3,
        "micro": 1e-6,
        "u": 1e-6,
        "nano": 1e-9,
        "n": 1e-9,
        "pico": 1e-12,
        "p": 1e-12,
    }.get(prefix, 1.0)
    return value * multiplier


def parse_command_fallback(command):
    text = command.lower()
    topology = "basic_circuit"
    if "band pass" in text or "band-pass" in text:
        topology = "band_pass_filter"
    elif "low pass" in text or "low-pass" in text:
        topology = "low_pass_filter"
    elif "high pass" in text or "high-pass" in text:
        topology = "high_pass_filter"

    voltage = _extract_value(r"(\\d+(?:\\.\\d+)?)\\s*(?:v|volt|volts)", text, default=1.0)
    frequency = _extract_value(r"(\\d+(?:\\.\\d+)?)\\s*(?:khz|kilohertz)", text)
    if frequency is not None:
        frequency *= 1000
    else:
        frequency = _extract_value(r"(\\d+(?:\\.\\d+)?)\\s*(?:hz)", text, default=25000.0)

    r_value = _parse_resistance(text, default=1.0)
    c_value = _parse_capacitance(text, default=100e-6)

    if topology == "band_pass_filter":
        return {"topology": topology, "R1": r_value, "R2": r_value, "C1": c_value, "C2": c_value, "V": voltage, "freq": frequency}
    if topology in {"low_pass_filter", "high_pass_filter"}:
        return {"topology": topology, "R": r_value, "C": c_value, "V": voltage, "freq": frequency}
    return {"V": 5, "R": 1, "C": 2, "topology": "basic_circuit"}


def _sanitize_components(components):
    if not isinstance(components, dict):
        raise ValueError("Parsed content is not a dictionary")

    cleaned = {}
    for key, value in components.items():
        if key not in ALLOWED_COMPONENT_KEYS:
            continue
        if key in {"topology", "V_type"}:
            cleaned[key] = str(value)
            continue
        if isinstance(value, (int, float)):
            cleaned[key] = float(value)
            continue
        if isinstance(value, str):
            try:
                cleaned[key] = float(value)
            except Exception:
                continue

    topology = cleaned.get("topology", "basic_circuit")
    if topology not in SUPPORTED_TOPOLOGIES:
        topology = "basic_circuit"
    cleaned["topology"] = topology

    if topology == "low_pass_filter":
        cleaned.setdefault("R", 1)
        cleaned.setdefault("C", 100e-6)
        cleaned.setdefault("V", 1)
        cleaned.setdefault("freq", 25000)
    elif topology == "high_pass_filter":
        cleaned.setdefault("R", 1)
        cleaned.setdefault("C", 100e-6)
        cleaned.setdefault("V", 1)
        cleaned.setdefault("freq", 25000)
    elif topology == "band_pass_filter":
        cleaned.setdefault("R1", 1)
        cleaned.setdefault("R2", 1)
        cleaned.setdefault("C1", 100e-6)
        cleaned.setdefault("C2", 100e-6)
        cleaned.setdefault("V", 1)
        cleaned.setdefault("freq", 25000)
    else:
        cleaned.setdefault("V", 5)
        cleaned.setdefault("R", 1)
        cleaned.setdefault("C", 2)

    return cleaned


def _parse_model_response(response_text):
    if not response_text:
        raise ValueError("Empty model response")
    start = response_text.find("{")
    end = response_text.rfind("}") + 1
    if start == -1 or end <= start:
        raise ValueError("No dictionary/JSON object found in model response")

    payload = response_text[start:end].strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return ast.literal_eval(payload)


def parse_command(command):
    if not command or not command.strip():
        return {"V": 5, "R": 1, "C": 2, "topology": "basic_circuit"}

    lowered = command.lower()
    if "simple circuit" in lowered or "basic circuit" in lowered:
        return {"V": 5, "R": 1, "C": 2, "topology": "basic_circuit"}

    if MODEL is None:
        return parse_command_fallback(command)

    prompt = '''
    Extract circuit component values and topology from this command: "{}"

    Rules:
    - Return STRICT JSON only (no markdown, no prose, no code block)
    - Interpret common units (k, m, u, n, p)
    - Support circuit topologies from the Circuits-LTSpice repository:
      * low_pass_filter: RC Low Pass Filter (default R=1, C=100uF)
      * high_pass_filter: RC High Pass Filter
      * band_pass_filter: RC Band Pass Filter
    - Include component specifications appropriate for each topology
    - For low_pass_filter: R, C, V (sine amplitude), freq (frequency in Hz)
    - For high_pass_filter: R, C, V
    - For band_pass_filter: R1, R2, C1, C2, V (sine amplitude), freq (frequency in Hz)
    Return ONLY one JSON object with no additional text or formatting.
    '''.format(command)

    response_text = ""
    try:
        response = MODEL.generate_content(prompt)
        response_text = (response.text or "").strip()
        return _sanitize_components(_parse_model_response(response_text))
    except Exception as exc:
        logger.warning("Gemini parsing error: %s", exc)
        if response_text:
            logger.debug("Raw model response: %s", response_text)
        return parse_command_fallback(command)
