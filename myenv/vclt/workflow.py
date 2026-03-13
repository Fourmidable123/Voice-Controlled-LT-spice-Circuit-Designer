import os
import time
import json
import re

import speech_recognition as sr
from pydub import AudioSegment

from vclt.config import CIRCUIT_DIR
from vclt.ltspice import open_in_ltspice
from vclt.parser import parse_command
from vclt.schematic import generate_circuit_schematic
from vclt.template_db import get_template_library_status, match_template


def _extract_template_overrides(query_text):
    """Extract generic component overrides from natural text for template circuits.

    Handles:
    - Indexed keys: R1=10k, C2 100n, L1 47u, V1 12V
    - Generic phrases: "1k resistors", "100n capacitors", "5V supply"
    - Boost phrases: "12V input", "24V output"
    """
    text = (query_text or "").lower()
    if not text:
        return {}

    # Normalize frequent spoken/unit variants to compact tokens.
    replacements = {
        "kilo ohm": "kohm",
        "kilo-ohm": "kohm",
        "mega ohm": "megohm",
        "mega-ohm": "megohm",
        "nano farad": "nanofarad",
        "micro farad": "microfarad",
        "pico farad": "picofarad",
        "micro henry": "microhenry",
        "milli henry": "millihenry",
        "volts": "v",
        "volt": "v",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    value_patterns = {
        "R": r"[0-9]*\.?[0-9]+\s*(?:k|kohm|ohm|meg|megohm|m)?",
        "C": r"[0-9]*\.?[0-9]+\s*(?:f|u|n|p|m|microfarad|nanofarad|picofarad)?",
        "L": r"[0-9]*\.?[0-9]+\s*(?:h|u|m|microhenry|millihenry)?",
        "V": r"[0-9]*\.?[0-9]+\s*(?:mv|v)?",
    }

    def _normalize_token(raw, kind):
        if raw is None:
            return None
        token = raw.strip().lower().replace(" ", "")

        token = token.replace("megohm", "meg")
        token = token.replace("kohm", "k")
        token = token.replace("ohm", "")
        token = token.replace("nanofarad", "n")
        token = token.replace("microfarad", "u")
        token = token.replace("picofarad", "p")
        token = token.replace("microhenry", "u")
        token = token.replace("millihenry", "m")

        if kind == "V" and token.endswith("v"):
            token = token[:-1]

        return token

    overrides = {}
    explicit_types = set()

    # 1) Indexed component assignments (R1, C2, L1, V1).
    # Require either a separator (=, :, is) or whitespace after the index to avoid
    # misreading tokens like "C10n" as "C1 = 0n".
    for kind, val_pat in value_patterns.items():
        patterns = [
            rf"\b{kind}\s*(\d+)\s*(?:=|is|:)\s*({val_pat})",
            rf"\b{kind}\s*(\d+)\s+({val_pat})",
        ]
        for pattern in patterns:
            for idx, raw in re.findall(pattern, text, flags=re.IGNORECASE):
                key = f"{kind}{idx}"
                norm = _normalize_token(raw, kind)
                if norm:
                    overrides[key.upper()] = norm
                    explicit_types.add(kind)

    # 1a) Non-indexed explicit assignments: R=4.7k, C=100n, V=5V
    for kind, val_pat in value_patterns.items():
        patterns = [
            rf"\b{kind}\b\s*(?:=|is|:)\s*({val_pat})",
            rf"\b{kind}\b\s+({val_pat})",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                norm = _normalize_token(m.group(1), kind)
                if norm:
                    overrides.setdefault(kind, norm)

    # 1a-bis) Forms like C10 nanofarad, R4.7 kilo-ohm, L22 microhenry
    unit_word_map = {
        "R": r"(?:k|kohm|ohm|meg|megohm|m)",
        "C": r"(?:f|u|n|p|m|microfarad|nanofarad|picofarad)",
        "L": r"(?:h|u|m|microhenry|millihenry)",
        "V": r"(?:mv|v)",
    }
    for kind, unit_pat in unit_word_map.items():
        m = re.search(rf"\b{kind}\s*([0-9]*\.?[0-9]+)\s*({unit_pat})\b", text, flags=re.IGNORECASE)
        if m and kind not in explicit_types:
            norm = _normalize_token(f"{m.group(1)}{m.group(2)}", kind)
            if norm:
                overrides[kind] = norm

    # 1b) Generic attached forms like C10n, R4.7k, L22u, V5.
    for kind, val_pat in value_patterns.items():
        m = re.search(rf"\b{kind}([0-9]*\.?[0-9]+(?:[a-zA-Z]+)?)\b", text, flags=re.IGNORECASE)
        if m and kind not in explicit_types and kind not in overrides:
            norm = _normalize_token(m.group(1), kind)
            if norm:
                overrides[kind] = norm

    # 2) Generic component phrases apply by type (all R*, C*, L* unless explicitly overridden).
    generic_phrases = [
        ("R", r"([0-9]*\.?[0-9]+\s*(?:k|kohm|ohm|meg|megohm|m)?)\s*(?:resistor|resistors|resistance)\b"),
        ("C", r"([0-9]*\.?[0-9]+\s*(?:f|u|n|p|m|microfarad|nanofarad|picofarad)?)\s*(?:capacitor|capacitors|capacitance)\b"),
        ("L", r"([0-9]*\.?[0-9]+\s*(?:h|u|m|microhenry|millihenry)?)\s*(?:inductor|inductors|inductance)\b"),
    ]
    for kind, pattern in generic_phrases:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m and kind not in explicit_types and kind not in overrides:
            norm = _normalize_token(m.group(1), kind)
            if norm:
                overrides[kind] = norm

    # 2b) RA/RB aliases (common in 555 descriptions)
    ra = re.search(r"\bra\b\s*(?:=|is|:)?\s*([0-9]*\.?[0-9]+\s*(?:k|kohm|ohm|meg|megohm|m)?)", text, flags=re.IGNORECASE)
    rb = re.search(r"\brb\b\s*(?:=|is|:)?\s*([0-9]*\.?[0-9]+\s*(?:k|kohm|ohm|meg|megohm|m)?)", text, flags=re.IGNORECASE)
    if ra and "R1" not in overrides:
        overrides["R1"] = _normalize_token(ra.group(1), "R")
    if rb and "R2" not in overrides:
        overrides["R2"] = _normalize_token(rb.group(1), "R")

    # 3) Friendly aliases for 555 prompts.
    if "RA" in overrides and "R1" not in overrides:
        overrides["R1"] = overrides["RA"]
    if "RB" in overrides and "R2" not in overrides:
        overrides["R2"] = overrides["RB"]

    # 4) Supply / input / output voltages.
    supply = re.search(r"(?:\bvcc\b|\bsupply\b)\s*(?:=|is|:)?\s*([0-9]*\.?[0-9]+\s*(?:mv|v)?)", text, flags=re.IGNORECASE)
    if supply:
        v = _normalize_token(supply.group(1), "V")
        overrides.setdefault("V", v)
        overrides.setdefault("V1", v)

    vin_match = re.search(r"([0-9]*\.?[0-9]+\s*(?:mv|v)?)\s*(?:input|in)\b", text, flags=re.IGNORECASE)
    if not vin_match:
        vin_match = re.search(r"(?:input|in)\s*(?:=|is|:)?\s*([0-9]*\.?[0-9]+\s*(?:mv|v)?)", text, flags=re.IGNORECASE)
    if vin_match:
        vin = _normalize_token(vin_match.group(1), "V")
        overrides["VIN"] = vin
        overrides["VD"] = vin
        overrides.setdefault("V", vin)
        overrides.setdefault("V1", vin)

    vout_match = re.search(r"([0-9]*\.?[0-9]+\s*(?:mv|v)?)\s*(?:output|out)\b", text, flags=re.IGNORECASE)
    if not vout_match:
        vout_match = re.search(r"(?:output|out)\s*(?:=|is|:)?\s*([0-9]*\.?[0-9]+\s*(?:mv|v)?)", text, flags=re.IGNORECASE)
    if vout_match:
        overrides["VOUT_TARGET"] = _normalize_token(vout_match.group(1), "V")

    return {k: v for k, v in overrides.items() if v}


def _apply_template_overrides(template_content, overrides):
    if not overrides:
        return template_content

    lines = template_content.splitlines()
    out = []
    current_inst = None

    # If both Vin and desired Vout are provided, update duty parameter for boost templates:
    # ideal boost relation Vout = Vin/(1-D) -> D = 1 - Vin/Vout
    vin_raw = overrides.get("VIN")
    vout_raw = overrides.get("VOUT_TARGET")
    duty_override = None
    try:
        if vin_raw is not None and vout_raw is not None:
            vin = float(vin_raw)
            vout = float(vout_raw)
            if vin > 0 and vout > vin:
                d = 1.0 - (vin / vout)
                # keep sane switching duty bounds
                d = max(0.05, min(0.9, d))
                duty_override = f"{d:.3f}".rstrip("0").rstrip(".")
    except Exception:
        duty_override = None

    for line in lines:
        inst_match = re.match(r"SYMATTR\s+InstName\s+(\S+)", line)
        if inst_match:
            current_inst = inst_match.group(1)
            out.append(line)
            continue

        val_match = re.match(r"SYMATTR\s+Value\s+(.+)$", line)
        if val_match and current_inst:
            inst_upper = current_inst.upper()
            replacement = None
            current_value = val_match.group(1).strip()

            if inst_upper in overrides:
                replacement = overrides[inst_upper]
            elif inst_upper == "VD" and "VIN" in overrides:
                replacement = overrides["VIN"]
            elif inst_upper.startswith("R") and "R" in overrides and re.match(r"^[0-9]*\.?[0-9]+(?:[a-zA-Z]+)?$", current_value):
                replacement = overrides["R"]
            elif inst_upper.startswith("C") and "C" in overrides:
                replacement = overrides["C"]
            elif inst_upper.startswith("L") and "L" in overrides and re.match(r"^[0-9]*\.?[0-9]+(?:[a-zA-Z]+)?$", current_value):
                replacement = overrides["L"]
            elif (
                inst_upper.startswith("V")
                and "V" in overrides
                and re.match(r"^[0-9]*\.?[0-9]+(?:[a-zA-Z]+)?$", current_value)
            ):
                # Only replace simple DC values; do not overwrite expressions like PULSE(...)
                replacement = overrides["V"]

            if replacement is not None:
                out.append(f"SYMATTR Value {replacement}")
                continue

        # Update duty parameter text directive if requested
        if duty_override is not None and re.search(r"!\.param\s+D\s*=", line, flags=re.IGNORECASE):
            line = re.sub(r"(?i)!\.param\s+D\s*=\s*[^\r\n]+", f"!.param D = {duty_override}", line)

        out.append(line)

    return "\n".join(out)


def _normalize_transient_stop_time(value):
    text = (value or "").strip().lower()
    if not text:
        return "0.2m"
    text = text.replace(" ", "")
    text = text.replace("sec", "s").replace("secs", "s").replace("second", "s").replace("seconds", "s")
    text = text.replace("usec", "u").replace("us", "u")
    # Accept LTspice-style suffixes (s, m, u, n, p, f) and common explicit forms like ms.
    if re.match(r"^[0-9]*\.?[0-9]+(?:e[+\-]?[0-9]+)?(?:s|ms|m|u|n|p|f)?$", text):
        if text.endswith("ms"):
            return text[:-2] + "m"
        return text
    return "0.2m"


def _apply_transient_stop_time(safe_content, transient_stop_time):
    stop_time = _normalize_transient_stop_time(transient_stop_time)

    # Replace only the first .tran directive-like token (active or commented form).
    updated, count = re.subn(
        r"(?i)([;!]?\.tran)\s+[^\r\n]*",
        f"!.tran 0 {stop_time}",
        safe_content,
        count=1,
    )
    if count > 0:
        return updated

    # Fallback if no directive exists in content.
    return safe_content + f"\n!.tran 0 {stop_time}\n"


def _format_value_for_ltspice(value, kind=None):
    """Format numeric value into short LTspice-friendly suffix form.
    kind: 'resistance', 'capacitance', 'inductance', 'frequency', 'voltage' or None
    Returns a string like '4.7k', '100n', '1u', '10Meg'
    """
    try:
        v = float(value)
    except Exception:
        return str(value)

    # Resistances
    if kind == 'resistance':
        if abs(v) >= 1e6:
            return f"{v/1e6:g}meg"
        if abs(v) >= 1e3:
            return f"{v/1e3:g}k"
        if abs(v) < 1 and v != 0:
            return f"{v*1e3:g}m"
        return f"{v:g}"

    # Capacitance
    if kind == 'capacitance':
        if abs(v) >= 1e-3:
            return f"{v/1e-3:g}m"  # millifarads (rare)
        if abs(v) >= 1e-6:
            return f"{v/1e-6:g}u"
        if abs(v) >= 1e-9:
            return f"{v/1e-9:g}n"
        if abs(v) >= 1e-12:
            return f"{v/1e-12:g}p"
        return f"{v:g}"

    # Inductance
    if kind == 'inductance':
        if abs(v) >= 1e-3:
            return f"{v/1e-3:g}m"
        if abs(v) >= 1e-6:
            return f"{v/1e-6:g}u"
        if abs(v) >= 1e-9:
            return f"{v/1e-9:g}n"
        return f"{v:g}"

    # Frequency
    if kind == 'frequency':
        if abs(v) >= 1e6:
            return f"{v/1e6:g}MegHz"
        if abs(v) >= 1e3:
            return f"{v/1e3:g}kHz"
        return f"{v:g}Hz"

    # Voltage or default: keep simple float representation if integer-like, else use plain
    if kind == 'voltage':
        if v.is_integer():
            return str(int(v))
        return f"{v:g}"

    # Generic fallback
    if v.is_integer():
        return str(int(v))
    return f"{v:g}"


def _save_content_to_circuit_dir(
    schematic_content,
    analysis_mode="transient",
    transient_stop_time="0.2m",
    file_prefix="circuit",
    ensure_probes=True,
    format_component_values=True,
    unescape_backslash_newlines=True,
):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    circuit_filename = f"{file_prefix}_{timestamp}.asc"
    circuit_path = os.path.join(CIRCUIT_DIR, circuit_filename)
    # For generated schematics, convert escaped newlines to real newlines.
    # For template copies, keep literal "\\n" because LTspice TEXT records may rely on it.
    safe_content = schematic_content
    if unescape_backslash_newlines:
        safe_content = safe_content.replace("\\n", "\n")
    if not safe_content.endswith("\n"):
        safe_content += "\n"

    if ensure_probes:
        # Ensure there is an explicit ground flag (0) and a common output label (OUT/Vout/Output)
        try:
            has_ground = re.search(r"^FLAG\s+.*\b0\b", safe_content, flags=re.MULTILINE) is not None
            has_output_label = re.search(r"\b(out|vout|output)\b", safe_content, flags=re.IGNORECASE) is not None
            additions = []
            if not has_ground:
                additions.append("FLAG 80 272 0")
            if not has_output_label:
                additions.append("FLAG 400 48 OUT")
            if additions:
                additions.append("TEXT 16 360 Left 2 ; Probes: ground=0, output=OUT. Open in LTspice and click node to view waveform.")
                safe_content = safe_content + "\n".join(additions) + "\n"
        except Exception:
            pass

    if format_component_values:
        # Post-process SYMATTR Value lines to use human-friendly unit suffixes when possible
        try:
            lines = safe_content.splitlines()
            inst_name = None
            processed = []
            for line in lines:
                m_inst = re.match(r"SYMATTR\s+InstName\s+(\S+)", line)
                if m_inst:
                    inst_name = m_inst.group(1)
                    processed.append(line)
                    continue
                m_val = re.match(r"SYMATTR\s+Value\s+(.+)$", line)
                if m_val:
                    raw_val = m_val.group(1).strip()
                    formatted = raw_val
                    if re.match(r"^[\d\.+\-eE]+$", raw_val) or re.match(r"^[\d\.+\-eE]+e[\+\-]?\d+$", raw_val):
                        kind = None
                        if inst_name:
                            lname = inst_name.lower()
                            if lname.startswith('r'):
                                kind = 'resistance'
                            elif lname.startswith('c'):
                                kind = 'capacitance'
                            elif lname.startswith('l'):
                                kind = 'inductance'
                            elif lname.startswith('v'):
                                kind = 'voltage'
                        try:
                            formatted = _format_value_for_ltspice(float(raw_val), kind=kind)
                        except Exception:
                            formatted = raw_val
                    else:
                        try:
                            fval = float(raw_val)
                            kind = None
                            if inst_name:
                                lname = inst_name.lower()
                                if lname.startswith('r'):
                                    kind = 'resistance'
                                elif lname.startswith('c'):
                                    kind = 'capacitance'
                            formatted = _format_value_for_ltspice(fval, kind=kind)
                        except Exception:
                            formatted = raw_val
                    processed.append(f"SYMATTR Value {formatted}")
                    continue
                processed.append(line)
            safe_content = "\n".join(processed) + "\n"
        except Exception:
            pass

    # Ensure only one active analysis directive based on requested mode.
    try:
        mode = (analysis_mode or "transient").strip().lower()
        if mode not in {"transient", "ac"}:
            mode = "transient"

        if mode == "ac":
            # Activate AC and comment transient.
            safe_content = re.sub(r'(?i);\.ac', '!.ac', safe_content)
            safe_content = re.sub(r'(?i)!\.tran', ';.tran', safe_content)
            safe_content = re.sub(r'(?m)^\s*\.tran\b', ';.tran', safe_content)
            safe_content = re.sub(r'(?m)^\s*;\s*\.ac\b', '.ac', safe_content)
            safe_content = re.sub(r'(?m)^\s*\.op\b', ';.op', safe_content)
        else:
            # Activate transient and comment AC/OP.
            safe_content = re.sub(r'(?i);\.tran', '!.tran', safe_content)
            safe_content = re.sub(r'(?i)!\.ac', ';.ac', safe_content)
            safe_content = re.sub(r'(?m)^\s*\.ac\b', ';.ac', safe_content)
            safe_content = re.sub(r'(?m)^\s*\.op\b', ';.op', safe_content)
            safe_content = _apply_transient_stop_time(safe_content, transient_stop_time)
    except Exception:
        pass

    with open(circuit_path, "w", newline="\n") as file_obj:
        file_obj.write(safe_content)
    return circuit_filename, circuit_path


def _save_schematic(components, analysis_mode="transient", transient_stop_time="0.2m"):
    schematic_content = generate_circuit_schematic(components)
    return _save_content_to_circuit_dir(
        schematic_content,
        analysis_mode=analysis_mode,
        transient_stop_time=transient_stop_time,
        file_prefix="circuit",
        ensure_probes=True,
        format_component_values=True,
        unescape_backslash_newlines=True,
    )


def _save_template_copy(
    template_path,
    analysis_mode="transient",
    transient_stop_time="0.2m",
    query_text="",
):
    with open(template_path, "r", encoding="utf-8", errors="ignore") as file_obj:
        template_content = file_obj.read()

    overrides = _extract_template_overrides(query_text)
    if overrides:
        template_content = _apply_template_overrides(template_content, overrides)

    base_name = os.path.splitext(os.path.basename(template_path))[0]
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", base_name).strip("_").lower() or "template"
    return _save_content_to_circuit_dir(
        template_content,
        analysis_mode=analysis_mode,
        transient_stop_time=transient_stop_time,
        file_prefix=safe_name,
        ensure_probes=False,
        format_component_values=False,
        unescape_backslash_newlines=False,
    )


def _try_create_from_template(query_text, analysis_mode="transient", transient_stop_time="0.2m"):
    match = match_template(query_text)
    if not match:
        return None

    overrides = _extract_template_overrides(query_text)

    circuit_filename, circuit_path = _save_template_copy(
        match["path"],
        analysis_mode=analysis_mode,
        transient_stop_time=transient_stop_time,
        query_text=query_text,
    )
    _, message = open_in_ltspice(circuit_path)
    status = (
        "Template circuit opened successfully!\n"
        f"Matched template: {match['name']}\n"
        f"Category: {match['category']}\n"
        f"Match score: {match['score']}\n"
        f"Detected overrides: {overrides if overrides else 'none'}\n"
        f"Analysis mode: {analysis_mode}\n"
        f"Transient stop time: {_normalize_transient_stop_time(transient_stop_time)}\n"
        f"Source template: {match['relpath']}\n"
        f"Saved as: {circuit_filename}\n"
        f"{message}"
    )
    return status, ""


def process_text(text):
    if not text or not text.strip():
        return "Please enter a circuit description first."

    try:
        components = parse_command(text)
        topology = components.get("topology", "basic_circuit")
        circuit_filename, circuit_path = _save_schematic(components)
        _, message = open_in_ltspice(circuit_path)
        return (
            "Circuit created successfully!\n"
            f"Recognized: {text}\n"
            f"Topology: {topology}\n"
            f"Components: {components}\n"
            f"Saved as: {circuit_filename}\n"
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
                    "Circuit created successfully!\n"
                    f"Recognized: {command}\n"
                    f"Components: {components}\n"
                    f"Saved as: {circuit_filename}\n"
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
        return "### Parser Preview\nEnter text in the Text Input tab to preview extracted values."
    template_match = match_template(text)
    if template_match:
        return (
            "### Template Match Preview\n"
            f"- Input: `{text}`\n"
            f"- Matched Template: `{template_match['name']}`\n"
            f"- Category: `{template_match['category']}`\n"
            f"- Match Score: `{template_match['score']}`\n"
            f"- Source: `{template_match['relpath']}`"
        )
    components = parse_command(text)
    topology = components.get("topology", "basic_circuit")
    return (
        "### Parser Preview\n"
        f"- Input: `{text}`\n"
        f"- Topology: `{topology}`\n"
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
        return "\n".join(os.path.basename(path) for path in asc_files[:limit])
    except Exception as exc:
        return f"Could not list circuit files: {exc}"


def create_circuit_from_text(text, analysis_mode="transient", transient_stop_time="0.2m"):
    """Create circuit from text, open in LTspice. If parser used defaults, return parsed JSON for confirmation.
    Returns (status_message, parsed_components_json_or_empty)
    """
    if not text or not text.strip():
        return "Please enter a circuit description first.", ""
    try:
        template_result = _try_create_from_template(
            text,
            analysis_mode=analysis_mode,
            transient_stop_time=transient_stop_time,
        )
        if template_result is not None:
            return template_result

        components = parse_command(text)
        # If parser indicates defaults were used, do not save — return parsed components for confirmation
        if isinstance(components, dict) and components.get('defaults'):
            status = (
                "Parser could not reliably extract some values.\n"
                "Please confirm or edit the parsed component values below and click 'Confirm & Create Circuit'.\n"
                f"Parsed: {components}\n"
            )
            parsed_json = json.dumps(components, indent=2)
            return status, parsed_json

        topology = components.get("topology", "basic_circuit")
        circuit_filename, circuit_path = _save_schematic(
            components,
            analysis_mode=analysis_mode,
            transient_stop_time=transient_stop_time,
        )
        _, message = open_in_ltspice(circuit_path)
        status = (
            "Circuit created successfully!\n"
            f"Recognized: {text}\n"
            f"Topology: {topology}\n"
            f"Analysis mode: {analysis_mode}\n"
            f"Transient stop time: {_normalize_transient_stop_time(transient_stop_time)}\n"
            f"Components: {components}\n"
            f"Saved as: {circuit_filename}\n"
            f"{message}"
        )
        return status, ""
    except Exception as exc:
        return f"Error: {exc}", ""


def create_circuit_from_audio(audio_path, analysis_mode="transient", transient_stop_time="0.2m"):
    """Create circuit from audio input file, open in LTspice. If parser used defaults return parsed JSON for confirmation."""
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
                template_result = _try_create_from_template(
                    command,
                    analysis_mode=analysis_mode,
                    transient_stop_time=transient_stop_time,
                )
                if template_result is not None:
                    return template_result

                components = parse_command(command)
                if isinstance(components, dict) and components.get('defaults'):
                    status = (
                        "Parser could not reliably extract some values from audio.\n"
                        "Please confirm or edit the parsed component values below and click 'Confirm & Create Circuit'.\n"
                        f"Parsed: {components}\n"
                    )
                    parsed_json = json.dumps(components, indent=2)
                    return status, parsed_json

                circuit_filename, circuit_path = _save_schematic(
                    components,
                    analysis_mode=analysis_mode,
                    transient_stop_time=transient_stop_time,
                )
                _, message = open_in_ltspice(circuit_path)
                status = (
                    "Circuit created successfully!\n"
                    f"Recognized: {command}\n"
                    f"Analysis mode: {analysis_mode}\n"
                    f"Transient stop time: {_normalize_transient_stop_time(transient_stop_time)}\n"
                    f"Components: {components}\n"
                    f"Saved as: {circuit_filename}\n"
                    f"{message}"
                )
                return status, ""
            except sr.UnknownValueError:
                return "Could not understand audio", ""
            except sr.RequestError:
                return "Speech recognition service error", ""
            except Exception as exc:
                return f"Error: {exc}", ""
    finally:
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass


def confirm_and_save_from_json(json_text, analysis_mode="transient", transient_stop_time="0.2m"):
    """User confirms/edits parsed components JSON; save schematic and open in LTspice. Returns (status_message, recent_files_text)"""
    try:
        components = json.loads(json_text)
        circuit_filename, circuit_path = _save_schematic(
            components,
            analysis_mode=analysis_mode,
            transient_stop_time=transient_stop_time,
        )
        _, message = open_in_ltspice(circuit_path)
        status = (
            "Circuit created successfully!\n"
            f"Analysis mode: {analysis_mode}\n"
            f"Transient stop time: {_normalize_transient_stop_time(transient_stop_time)}\n"
            f"Components: {components}\n"
            f"Saved as: {circuit_filename}\n"
            f"{message}"
        )
        recent = list_recent_circuits()
        return status, recent
    except json.JSONDecodeError:
        return "Invalid JSON. Please fix the parsed components and try again.", list_recent_circuits()
    except Exception as exc:
        return f"Error saving circuit: {exc}", list_recent_circuits()


def get_library_status_text():
    return get_template_library_status()
