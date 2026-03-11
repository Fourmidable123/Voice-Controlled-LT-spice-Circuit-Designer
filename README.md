# Voice-Controlled LTspice Circuit Designer

A Python app that converts voice or text circuit requests into LTspice `.asc` schematics.

## Features

- Voice and text command input
- Natural-language parsing with AI-assisted and fallback rule-based modes
- Template-based LTspice schematic generation
- Local LTspice template library indexing from downloaded `.asc` collections
- Automatic LTspice launch support
- Gradio UI with parse preview and recent file list

## Project Structure

- `myenv/voice_circuit.py`: launcher entry point
- `myenv/requirements.txt`: Python dependencies
- `myenv/vclt/config.py`: shared constants, paths, logging, UI styles
- `myenv/vclt/parser.py`: command parsing and sanitization
- `myenv/vclt/schematic.py`: `.asc` template generation
- `myenv/vclt/ltspice.py`: LTspice path detection and launch
- `myenv/vclt/workflow.py`: orchestration for text/audio processing
- `myenv/vclt/ui.py`: Gradio interface

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

3. Set environment variables (recommended):

```bash
# Windows PowerShell
$env:GEMINI_API_KEY="your_api_key"
$env:LTSPICE_PATH="C:\\Program Files\\ADI\\LTspice\\LTspice.exe"
```

Optional template library override:

```bash
export LTSPICE_TEMPLATE_LIBRARY_DIR="/path/to/Circuits-LTSpice-master-2"
```

4. Run the app:

```bash
python myenv/voice_circuit.py
```

5. Open the local Gradio URL shown in the terminal.

## Example Prompts

- "RC low pass filter with R 10k and C 1uF"
- "RC high pass filter with 4.7k resistor and 100nF capacitor"
- "Basic RC circuit with 1k resistor and 10uF capacitor"

## Notes

- If `GEMINI_API_KEY` is not set, fallback parsing is used for common RC/filter commands.
- If LTspice is not found automatically, set `LTSPICE_PATH` manually.
- If a local template library is present, the UI will try to match your prompt to the closest downloaded `.asc` circuit before falling back to the built-in generator.
