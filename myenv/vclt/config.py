import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CIRCUIT_DIR = os.path.join(os.path.expanduser("~"), "ltspice_circuits")
os.makedirs(CIRCUIT_DIR, exist_ok=True)

SUPPORTED_TOPOLOGIES = {
    "basic_circuit",
    "low_pass_filter",
    "high_pass_filter",
    "band_pass_filter",
    "common_emitter",
    "boost_converter",
    "astable_multivibrator",
    "wien_oscillator",
    "full_bridge_rectifier",
}

ALLOWED_COMPONENT_KEYS = {
    "topology", "R", "R1", "R2", "C", "C1", "C2", "L", "V", "V_type", "freq"
}

CUSTOM_CSS = """
body {
    background: radial-gradient(circle at 10% 10%, #fdf3dd 0%, #f4f8ff 45%, #eef4f9 100%);
}
.hero {
    border: 1px solid #dce4ee;
    background: linear-gradient(130deg, #ffefd6 0%, #eaf4ff 55%, #edf9f3 100%);
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 10px;
}
.card {
    border: 1px solid #d8e1ea;
    border-radius: 14px;
    padding: 12px;
    background: #ffffffd9;
}
"""
