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


# Helpers for robust unit parsing
_WORDS = {
    'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
    'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
}


def _words_to_number(text):
    """Convert simple spoken numbers like 'four', 'four point seven' to float when possible."""
    text = text.strip().lower()
    if not text:
        return None
    # handle patterns like 'four point seven'
    if 'point' in text:
        parts = [p.strip() for p in text.split('point', 1)]
        left = _words_to_number(parts[0])
        right_text = parts[1]
        # convert each word on right to digits
        digits = []
        for tok in right_text.split():
            if tok in _WORDS:
                digits.append(_WORDS[tok])
            elif tok.isdigit():
                digits.append(tok)
        if left is None or not digits:
            return None
        try:
            return float(f"{int(left)}.{''.join(digits)}")
        except Exception:
            return None
    # single word maps
    if text in _WORDS:
        return float(_WORDS[text])
    # direct numeric string
    try:
        return float(text)
    except Exception:
        return None


def _parse_value_unit(text, value_type, default=None):
    """Parse a numeric value with common unit prefixes for different component types.
    value_type: 'resistance', 'capacitance', 'frequency', 'voltage'
    Returns a tuple (value, used_default).
    """
    if not text or not text.strip():
        return default, True
    txt = text.lower()

    # First, try unit-specific patterns to avoid capturing unrelated numbers (e.g. 4.7k for R when parsing C)
    m = None
    if value_type == 'capacitance':
        m = re.search(r"(\d+[\.,]?\d*)\s*(pF|nf|uF|µF|uf|pf|pico|nano|micro|farad|farads)\b", txt, flags=re.IGNORECASE)
    elif value_type == 'resistance':
        m = re.search(r"(\d+[\.,]?\d*)\s*(ohm|ohms|kohm|kohms|k|kilo|meg|mega|milli|m)\b", txt, flags=re.IGNORECASE)
    elif value_type == 'frequency':
        m = re.search(r"(\d+[\.,]?\d*)\s*(khz|mhz|hz|kilohertz|megahertz|hertz)\b", txt, flags=re.IGNORECASE)
    elif value_type == 'voltage':
        m = re.search(r"(\d+[\.,]?\d*)\s*(mv|v|volt|volts)\b", txt, flags=re.IGNORECASE)
    elif value_type == 'inductance':
        m = re.search(r"(\d+[\.,]?\d*)\s*(uh|uH|mh|mH|h|H|microhenry|millihenry|henry)\b", txt, flags=re.IGNORECASE)

    # If no unit-specific match, try to find a number that is mentioned near a clue word (capacitor/resistor/hz/volt)
    if not m:
        context_map = {
            'capacitance': r"(\d+[\.,]?\d*).{0,20}(?:capacitor|farad|f)",
            'resistance': r"(\d+[\.,]?\d*).{0,20}(?:resistor|ohm|ohms)",
            'frequency': r"(\d+[\.,]?\d*).{0,20}(?:hz|khz|kilohertz|mhz)",
            'voltage': r"(\d+[\.,]?\d*).{0,20}(?:v|volt|volts)",
        }
        pat = context_map.get(value_type)
        if pat:
            m = re.search(pat, txt, flags=re.IGNORECASE)

    # Final fallback: a generic numeric with a possible prefix (but only if nothing else found)
    if not m:
        m = re.search(r"(\d+[\.,]?\d*)\s*([kmnumptgµ]|mega|kilo|micro|nano|pico|mhz|khz|hz|mv|v)?\b", txt, flags=re.IGNORECASE)

    if not m:
        return default, True

    try:
        num_str = m.group(1).replace(',', '.')
        val = float(num_str)
    except Exception:
        return default, True

    unit_token = ''
    if m.lastindex and m.lastindex >= 2:
        unit_token = (m.group(2) or '').lower().strip() if m.group(2) else ''
    else:
        # try to extract a nearby unit word from the full match
        full = m.group(0).lower()
        unit_match = re.search(r"(pico|nano|micro|u|n|p|pf|nf|uf|khz|mhz|hz|k|kohm|ohm|v|mv|farad|ohms|kohms|meg|mega)", full)
        unit_token = unit_match.group(1) if unit_match else ''

    # normalize multiplier based on detected unit_token and value_type
    mult = 1.0
    if value_type == 'resistance':
        if unit_token in ('k', 'kilo', 'kohm', 'kohms'):
            mult = 1e3
        elif unit_token in ('meg', 'mega'):
            mult = 1e6
        elif unit_token in ('milli', 'm'):
            mult = 1e-3
    elif value_type == 'capacitance':
        if unit_token in ('p', 'pico', 'pf'):
            mult = 1e-12
        elif unit_token in ('n', 'nano', 'nf'):
            mult = 1e-9
        elif unit_token in ('u', 'µf', 'uf', 'micro', 'microfarad', 'uf'):
            mult = 1e-6
        elif unit_token in ('m', 'milli'):
            mult = 1e-3
    elif value_type == 'frequency':
        if unit_token in ('khz', 'k', 'kilohertz'):
            mult = 1e3
        elif unit_token in ('mhz', 'megahertz'):
            mult = 1e6
    elif value_type == 'voltage':
        if unit_token in ('mv',):
            mult = 1e-3
    elif value_type == 'inductance':
        if unit_token in ('mh', 'mhz', 'milli', 'mH'):
            mult = 1e-3
        elif unit_token in ('uh', 'uh|u', 'micro', 'u'):
            mult = 1e-6
        elif unit_token in ('h', 'henry'):
            mult = 1.0

    return val * mult, False


def _parse_resistance(text, default=1.0):
    val, used_default = _parse_value_unit(text, 'resistance', default)
    return val


def _parse_capacitance(text, default=100e-6):
    val, used_default = _parse_value_unit(text, 'capacitance', default)
    return val


def parse_command_fallback(command):
    text = command.lower()
    topology = "basic_circuit"
    if "band pass" in text or "band-pass" in text:
        topology = "band_pass_filter"
    elif "low pass" in text or "low-pass" in text:
        topology = "low_pass_filter"
    elif "high pass" in text or "high-pass" in text:
        topology = "high_pass_filter"

    # extract a voltage value like '5V' or '12 volts' (allow decimals)
    voltage = _extract_value(r"(\d+(?:\.\d+)?)\s*(?:v|volt|volts)", text, default=1.0)

    # frequency parsing - prefer khz or hz with units, default 25k
    freq_val, freq_defaulted = _parse_value_unit(text, 'frequency', default=25000.0)
    r_value, r_defaulted = _parse_value_unit(text, 'resistance', default=1.0)
    c_value, c_defaulted = _parse_value_unit(text, 'capacitance', default=100e-6)
    l_value, l_defaulted = _parse_value_unit(text, 'inductance', default=100e-6)
    
    # Track defaults used to enable prompting
    defaults = []
    if freq_defaulted:
        defaults.append('freq')
    if r_defaulted:
        defaults.append('R')
    if c_defaulted:
        defaults.append('C')
    if l_defaulted:
        defaults.append('L')

    if topology == "band_pass_filter":
        out = {"topology": topology, "R1": r_value, "R2": r_value, "C1": c_value, "C2": c_value, "V": voltage, "freq": freq_val}
        if defaults:
            out['defaults'] = defaults
        return out
    if topology in {"low_pass_filter", "high_pass_filter"}:
        out = {"topology": topology, "R": r_value, "C": c_value, "V": voltage, "freq": freq_val}
        if defaults:
            out['defaults'] = defaults
        return out
    return {"V": 5, "R": 1, "C": 2, "topology": "basic_circuit"}


def _sanitize_components(components):
    if not isinstance(components, dict):
        raise ValueError("Parsed content is not a dictionary")

    cleaned = {}
    defaults_list = []
    for key, value in components.items():
        if key not in ALLOWED_COMPONENT_KEYS and key != 'defaults':
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

    # if parser provided a 'defaults' list, mark those as defaults used
    if isinstance(components.get('defaults'), list):
        for k in components.get('defaults'):
            defaults_list.append(k)

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

    if defaults_list:
        cleaned['defaults'] = defaults_list

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
