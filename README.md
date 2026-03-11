# Voice-Controlled LTspice Circuit Designer

A Python app that converts voice or text circuit requests into LTspice `.asc` schematics.

## Features

- Voice and text command input
- Natural-language parsing with AI-assisted and fallback rule-based modes
- Template-based LTspice schematic generation
- Bundled curated LTspice template library (`template-library-curated`) for out-of-box use
- Template matching first, then fallback to built-in schematic generator
- Automatic LTspice launch support
- Gradio UI with parse preview and recent file list
- Simulation mode selector (`Transient` / `AC`) and editable transient stop time

## Project Structure

- `myenv/voice_circuit.py`: launcher entry point
- `myenv/requirements.txt`: Python dependencies
- `myenv/vclt/config.py`: shared constants, paths, logging, UI styles
- `myenv/vclt/parser.py`: command parsing and sanitization
- `myenv/vclt/schematic.py`: `.asc` template generation
- `myenv/vclt/template_db.py`: template indexing and fuzzy matching
- `myenv/vclt/ltspice.py`: LTspice path detection and launch
- `myenv/vclt/workflow.py`: orchestration for text/audio processing
- `myenv/vclt/ui.py`: Gradio interface
- `template-library-curated/`: packaged curated `.asc` templates used by default

## Requirements

- Python 3.10+
- LTspice installed (optional for file generation, required for auto-open)
- Microphone access (optional, only for voice input)

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r myenv/requirements.txt
```

3. Run the app:

```bash
PYTHONPATH=myenv python myenv/voice_circuit.py
```

4. Open the local Gradio URL shown in terminal (usually `http://127.0.0.1:7860`).

## Optional Environment Variables

Set only if you need them:

```bash
# Optional AI parsing (otherwise rule-based parser is used)
export GEMINI_API_KEY="your_api_key"

# Optional template library override
export LTSPICE_TEMPLATE_LIBRARY_DIR="/path/to/template-library"

# Optional curated mode toggle (1=enabled, 0=disabled)
export LTSPICE_TEMPLATE_CURATED_MODE=1

# Optional LTspice executable path override (mostly for Windows)
export LTSPICE_PATH="/path/to/LTspice"
```

## Example Prompts

- "wien oscillator with V=12V R=10k C=10nF"
- "boost converter 1 with Vin=5V L=100uH C=100uF"
- "window comparator with Vcc=12V"
- "RC lowpass with R=10k C=1uF"

## UI Usage

- Choose `Simulation Mode`:
	- `Transient`: app enables `.tran` and disables `.ac`
	- `AC`: app enables `.ac` and disables `.tran`
- Set `Transient Stop Time` (used only in transient mode), examples: `500u`, `20m`, `10s`.
- Enter text or voice command and create circuit.

## Notes

- If `GEMINI_API_KEY` is not set, fallback parsing is used for common RC/filter commands.
- If LTspice is not found automatically, set `LTSPICE_PATH` manually.
- The app uses `template-library-curated` by default, so users do not need to download the full external circuit pack.
