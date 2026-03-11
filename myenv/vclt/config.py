import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CIRCUIT_DIR = os.path.join(os.path.expanduser("~"), "ltspice_circuits")
os.makedirs(CIRCUIT_DIR, exist_ok=True)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEMPLATE_LIBRARY_DIR = os.getenv(
    "LTSPICE_TEMPLATE_LIBRARY_DIR",
    os.path.join(PROJECT_ROOT, "template-library-curated"),
)
TEMPLATE_INDEX_CACHE = os.path.join(CIRCUIT_DIR, "template_index.json")

# Curated template mode keeps common circuit families and filters out advanced/specialized libraries.
TEMPLATE_CURATED_MODE = os.getenv("LTSPICE_TEMPLATE_CURATED_MODE", "1").strip().lower() not in {"0", "false", "no"}
TEMPLATE_EXCLUDED_CATEGORY_KEYWORDS = {
    "power-lines",
    "lossless-transmission-line",
    "monte-carlo",
    "worst-case",
    "ask-modulator",
    "am-modulator",
    "rf-generators",
    "signal processing",
    "logic-circuits",
    "transformer",
    "temperature-variation",
    "miscellaneous",
    "soft-starters",
    "input stages",
    "pwm",
}
TEMPLATE_EXCLUDED_NAME_KEYWORDS = {
    "three-phase",
    "raw",
    "temporizzatore",
}

SUPPORTED_TOPOLOGIES = {
    "basic_circuit",
    "low_pass_filter",
    "high_pass_filter",
    "band_pass_filter",
}

ALLOWED_COMPONENT_KEYS = {
    "topology", "R", "R1", "R2", "C", "C1", "C2", "L", "V", "V_type", "freq"
}

CUSTOM_CSS = """
:root{
    --bg:#0b1220; /* page background */
    --panel:#0f1724; /* card background */
    --muted:#94a3b8; /* secondary text */
    --text:#e6eef8; /* primary text */
    --accent:#f59e0b; /* amber */
    --card-border: rgba(255,255,255,0.04);
}
/* Enforce a single font everywhere */
*,
*:before,
*:after {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

body {
    background: radial-gradient(circle at 10% 10%, #07101a 0%, var(--bg) 40%, #071220 100%);
    color: var(--text);
    margin: 0;
}
.hero h1 { font-size: 26px; color: var(--text); margin:0; }
.hero p { color: var(--muted); margin-top:8px; }

.card {
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 16px;
    background: linear-gradient(180deg, rgba(255,255,255,0.01), rgba(255,255,255,0.008));
    box-shadow: 0 8px 30px rgba(2,6,23,0.6);
}

/* Make Gradio UI text consistent */
.gradio-container { padding: 12px; }
.gradio-container .gr-block { font-size: 15px; }
.gradio-container, .gradio-container * { color: var(--text); }

/* Inputs and text areas */
.gradio-container .gr-textbox, .gradio-container textarea, .gradio-container .gr-input { 
    background: #09121a; 
    border: 1px solid rgba(255,255,255,0.04);
    color: var(--text);
    padding: 10px;
    border-radius: 8px;
    font-size: 14px;
}

/* Avoid truncation: allow wrapping and visible overflow for control labels */
.gradio-container .gr-button, .gradio-container .gr-label, .gradio-container .gr-markdown, .gradio-container .gr-textbox, .gradio-container .gr-audio {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
}

/* Ensure audio control status text wraps and expands */
.gradio-container .gr-audio .audio-status, .gradio-container .gr-audio .audio-controls {
    min-width: 0; /* allow flex children to shrink appropriately */
    white-space: normal !important;
}

/* Buttons */
.gradio-container .gr-button {
    background: var(--accent) !important;
    color: #0b1220 !important;
    border: none !important;
    font-weight: 700;
    padding: 10px 16px;
    border-radius: 8px;
}
.gradio-container .gr-button.secondary {
    background: transparent !important;
    color: var(--muted) !important;
    border: 1px solid rgba(255,255,255,0.03) !important;
}

/* Examples list */
.gradio-container .gr-examples { background: transparent; }
.gradio-container .gr-examples .gr-button { background: rgba(255,255,255,0.02); color: var(--text); }

/* Improve contrast for labels and small text */
label, .gradio-container .label { color: var(--muted); font-weight: 600; }

@media (min-width: 1000px) {
    .gradio-container { max-width: 1200px; margin: 0 auto; }
}
"""
