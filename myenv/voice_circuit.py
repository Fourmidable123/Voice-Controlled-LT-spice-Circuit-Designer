import speech_recognition as sr
import os
import google.generativeai as genai
from pydub import AudioSegment
import gradio as gr
import time
import subprocess

# Configure Gemini API
GEMINI_API_KEY = ''
genai.configure(api_key=GEMINI_API_KEY)

# Initialize Gemini model
model = genai.GenerativeModel('gemini-2.0-flash')

# LTspice path configuration
LTSPICE_PATH = os.getenv('LTSPICE_PATH', r'C:\Users\antony brijesh\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\LTspice\LTspice.lnk')

# Create a dedicated directory for circuit files
CIRCUIT_DIR = os.path.join(os.path.expanduser('~'), 'ltspice_circuits')
os.makedirs(CIRCUIT_DIR, exist_ok=True)
print(f"Using circuit directory: {CIRCUIT_DIR}")

def check_ltspice_installation():
    """
    Check if LTspice is installed and accessible
    """
    global LTSPICE_PATH
    
    if not os.path.exists(LTSPICE_PATH):
        # Try alternative common installation paths
        alt_paths = [
            r'C:\Program Files\LTspice\XVII\XVIIx64.exe',
            r'C:\Program Files (x86)\LTspice\XVII\XVIIx64.exe',
            r'C:\Program Files\LTspice\XVII\XVII.exe',
            r'C:\Program Files (x86)\LTspice\XVII\XVII.exe',
            r'C:\Users\antony brijesh\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\LTspice\LTspice.lnk'
        ]
        
        for path in alt_paths:
            if os.path.exists(path):
                LTSPICE_PATH = path
                return True, f"LTspice found at {path}"
        
        return False, f"LTspice not found. Please install LTspice or set the LTSPICE_PATH environment variable."
    return True, "LTspice installation found."

def generate_circuit_schematic(components):
    """
    Generate LTspice schematic from component specifications
    
    Args:
        components (dict): Dictionary containing component specifications
            - topology: Circuit topology (basic_circuit, low_pass_filter, high_pass_filter, etc.)
            - R: Resistor value in ohms
            - C: Capacitor value in farads
            - L: Inductor value in henries
            - V: Voltage source value in volts
            - V_type: Type of voltage source ('DC', 'AC', 'SINE', 'PULSE')
            - Component counts (R_count, C_count, etc.)
            - Special components (op-amps, transistors, diodes)
    
    Returns:
        str: LTspice schematic content
    """
    # Check if we're using a complex circuit topology
    topology = components.get('topology', 'basic_circuit')
    
    # List of topologies handled by generate_complex_circuit_netlist
    complex_topologies = [
        'common_emitter', 'boost_converter', 'astable_multivibrator',
        'wien_oscillator', 'full_bridge_rectifier'
    ]
    
    # If this is a complex topology, use the dedicated function
    if topology in complex_topologies:
        return generate_complex_circuit_netlist(topology, components)
    
    # Helper to format values as integers if possible
    def fmt(val):
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        if isinstance(val, int):
            return str(val)
        try:
            fval = float(val)
            if fval.is_integer():
                return str(int(fval))
        except Exception:
            pass
        return str(val)

    # Get the topology or default to basic circuit
    topology = components.get('topology', 'basic_circuit')
    
    # Initialize schematic
    schematic = []
    schematic.append("Version 4.1")
    schematic.append("SHEET 1 880 680")
    
    # Generate different circuit types based on topology
    if topology == 'low_pass_filter':
        # RC Low-Pass Filter based on reference file
        schematic.append("WIRE 208 48 80 48")
        schematic.append("WIRE 400 48 288 48")
        schematic.append("WIRE 80 112 80 48")
        schematic.append("WIRE 400 112 400 48")
        schematic.append("WIRE 80 272 80 192")
        schematic.append("WIRE 400 272 400 176")
        schematic.append("FLAG 80 272 0")
        schematic.append("FLAG 400 272 0")
        schematic.append("FLAG 400 48 OUT")
        schematic.append("SYMBOL voltage 80 96 R0")
        schematic.append("WINDOW 123 24 124 Left 2")
        schematic.append("WINDOW 39 0 0 Left 2")
        schematic.append("SYMATTR Value2 AC 1")
        schematic.append("SYMATTR InstName Vin")
        v_type = components.get('V_type', 'SINE')
        if v_type == 'SINE':
            schematic.append(f"SYMATTR Value {v_type}(1 {fmt(components.get('V', 1))} {fmt(components.get('freq', 25000))})")
        else:
            schematic.append(f"SYMATTR Value {fmt(components.get('V', 1))}")
        schematic.append("SYMBOL res 304 32 R90")
        schematic.append("WINDOW 0 0 56 VBottom 2")
        schematic.append("WINDOW 3 32 56 VTop 2")
        schematic.append("SYMATTR InstName R1")
        schematic.append(f"SYMATTR Value {fmt(components.get('R', 1))}")
        schematic.append("SYMBOL cap 384 112 R0")
        schematic.append("SYMATTR InstName C1")
        schematic.append(f"SYMATTR Value {fmt(components.get('C', 100e-6))}")
        schematic.append("TEXT 72 328 Left 2 !.tran 0 0.1 0 0.0001")
        schematic.append("TEXT 72 352 Left 2 !.ac dec 100 1 100k")
    elif topology == 'high_pass_filter':
        # RC High-Pass Filter based on reference file
        schematic.append("WIRE 192 48 80 48")
        schematic.append("WIRE 352 48 256 48")
        schematic.append("WIRE 464 48 352 48")
        schematic.append("WIRE 80 112 80 48")
        schematic.append("WIRE 352 112 352 48")
        schematic.append("WIRE 80 272 80 192")
        schematic.append("WIRE 352 272 352 192")
        schematic.append("FLAG 80 272 0")
        schematic.append("FLAG 352 272 0")
        schematic.append("FLAG 464 48 Output_high_pass")
        schematic.append("IOPIN 464 48 Out")
        schematic.append("SYMBOL voltage 80 96 R0")
        schematic.append("WINDOW 123 24 124 Left 2")
        schematic.append("WINDOW 39 0 0 Left 2")
        schematic.append("SYMATTR Value2 AC 1")
        schematic.append("SYMATTR InstName Vin")
        v_type = components.get('V_type', 'SINE')
        if v_type == 'SINE':
            schematic.append(f"SYMATTR Value {v_type}(1 {fmt(components.get('V', 1))} {fmt(components.get('freq', 25000))})")
        else:
            schematic.append(f"SYMATTR Value {fmt(components.get('V', 1))}")
        schematic.append("SYMBOL res 336 96 R0")
        schematic.append("SYMATTR InstName R1")
        schematic.append(f"SYMATTR Value {fmt(components.get('R', 1))}")
        schematic.append("SYMBOL cap 192 64 R270")
        schematic.append("WINDOW 0 32 32 VTop 2")
        schematic.append("WINDOW 3 0 32 VBottom 2")
        schematic.append("SYMATTR InstName C1")
        schematic.append(f"SYMATTR Value {fmt(components.get('C', 100e-6))}")
        schematic.append("TEXT 464 264 Left 2 !.ac dec 1000 10 100k")
    elif topology == 'band_pass_filter':
        # RC Band-Pass Filter based on reference file
        schematic.append("WIRE 176 48 80 48")
        schematic.append("WIRE 352 48 240 48")
        schematic.append("WIRE 448 48 352 48")
        schematic.append("WIRE 592 48 528 48")
        schematic.append("WIRE 80 112 80 48")
        schematic.append("WIRE 352 112 352 48")
        schematic.append("WIRE 592 112 592 48")
        schematic.append("WIRE 80 272 80 192")
        schematic.append("WIRE 352 272 352 192")
        schematic.append("WIRE 592 272 592 176")
        schematic.append("FLAG 80 272 0")
        schematic.append("FLAG 352 272 0")
        schematic.append("FLAG 592 272 0")
        schematic.append("FLAG 592 48 OUT")
        schematic.append("SYMBOL voltage 80 96 R0")
        schematic.append("WINDOW 123 24 124 Left 2")
        schematic.append("WINDOW 39 0 0 Left 2")
        schematic.append("SYMATTR Value2 AC 1")
        schematic.append("SYMATTR InstName V1")
        v_type = components.get('V_type', 'SINE')
        if v_type == 'SINE':
            schematic.append(f"SYMATTR Value {v_type}(1 {fmt(components.get('V', 1))} {fmt(components.get('freq', 25000))})")
        else:
            schematic.append(f"SYMATTR Value {fmt(components.get('V', 1))}")
        schematic.append("SYMBOL res 544 32 R90")
        schematic.append("WINDOW 0 0 56 VBottom 2")
        schematic.append("WINDOW 3 32 56 VTop 2")
        schematic.append("SYMATTR InstName R1")
        schematic.append(f"SYMATTR Value {fmt(components.get('R1', 1))}")
        schematic.append("SYMBOL cap 576 112 R0")
        schematic.append("SYMATTR InstName C1")
        schematic.append(f"SYMATTR Value {fmt(components.get('C1', 100e-6))}")
        schematic.append("SYMBOL cap 240 32 R90")
        schematic.append("WINDOW 0 0 32 VBottom 2")
        schematic.append("WINDOW 3 32 32 VTop 2")
        schematic.append("SYMATTR InstName C2")
        schematic.append(f"SYMATTR Value {fmt(components.get('C2', 100e-6))}")
        schematic.append("SYMBOL res 336 96 R0")
        schematic.append("SYMATTR InstName R2")
        schematic.append(f"SYMATTR Value {fmt(components.get('R2', 1))}")
        schematic.append("TEXT 80 320 Left 2 !.tran 0 0.1 0 0.0001")
        schematic.append("TEXT 80 344 Left 2 !.ac dec 100 1 100k")
        
    else:
        # Default basic circuit from Draft1.asc
        schematic.append("WIRE 208 128 64 128")
        schematic.append("WIRE 64 160 64 128")
        schematic.append("WIRE 208 240 208 208")
        schematic.append("WIRE 64 304 64 240")
        schematic.append("WIRE 208 304 64 304")
        schematic.append("WIRE 208 320 208 304")
        schematic.append("FLAG 208 320 0")
        schematic.append("SYMBOL voltage 64 144 R0")
        schematic.append("SYMATTR InstName V1")
        schematic.append("SYMATTR Value 5")
        schematic.append("SYMBOL res 192 112 R0")
        schematic.append("SYMATTR InstName R1")
        schematic.append("SYMATTR Value 1")
        schematic.append("SYMBOL cap 192 240 R0")
        schematic.append("SYMATTR InstName C1")
        schematic.append("SYMATTR Value 2")
        schematic.append("TEXT 24 344 Left 2 !.tran 10")
    
    return '\n'.join(schematic)

def parse_command_with_gemini_v2(command):
    """
    Enhanced version of parse_command_with_gemini with support for netlists from Circuits-LTSpice
    
    Args:
        command (str): Recognized speech command
    
    Returns:
        dict: Component specifications and circuit topology
    """
    prompt = '''
    Extract circuit component values and topology from this command: '{}'
    
    Rules:
    - Return a Python dictionary with component values and circuit topology
    - Interpret common units (k, m, u, n, p)
    - Support circuit topologies from the Circuits-LTSpice repository:
      * low_pass_filter: RC Low Pass Filter (default R=1, C=100µF)
      * high_pass_filter: RC High Pass Filter
      * band_pass_filter: RC Band Pass Filter
    - Include component specifications appropriate for each topology
    - For low_pass_filter: R, C, V (sine amplitude), freq (frequency in Hz)
    - For high_pass_filter: R, C, V
    - For band_pass_filter: R1, R2, C1, C2, V (sine amplitude), freq (frequency in Hz)
    
    Examples:
    "RC low pass filter with 10 ohm resistor and 47 microfarad capacitor" -> {{"topology": "low_pass_filter", "R": 10, "C": 47e-6, "V": 1, "freq": 25000}}
    "RC high pass filter with 4.7k resistor and 0.1uF capacitor" -> {{"topology": "high_pass_filter", "R": 4.7e3, "C": 0.1e-6}}
    "RC band pass filter with 1 ohm resistors and 100uF capacitors" -> {{"topology": "band_pass_filter", "R1": 1, "R2": 1, "C1": 100e-6, "C2": 100e-6, "V": 1, "freq": 25000}}
    Return ONLY the dictionary for the command, with no additional text or formatting.
    '''.format(command)
    
    try:
        response = model.generate_content(prompt)
        # Clean up the response to extract just the dictionary
        response_text = response.text.strip()
        
        # Remove any markdown formatting
        if "```" in response_text:
            for line in response_text.split('\n'):
                if '{' in line and '}' in line:
                    response_text = line.strip()
                    break
            if "```" in response_text:
                response_text = response_text.replace("```python", "").replace("```", "").strip()
        
        # Remove any text before { and after }
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end != 0:
            response_text = response_text[start:end]
        
        # Clean up any remaining non-dictionary text
        response_text = response_text.strip()
        
        print(f"Parsed response: {response_text}")  # Debug print
        
        # Safely evaluate the dictionary string
        components = eval(response_text)
        
        # Validate the components
        if not isinstance(components, dict):
            raise ValueError("Response is not a dictionary")
        
        # Set default frequency for low pass filter if not specified
        if components.get('topology') == 'low_pass_filter' and 'freq' not in components:
            components['freq'] = 25000  # Default to 25kHz as in reference
            
        # Check for basic circuit case and set topology explicitly
        if "simple circuit" in command.lower() or "basic circuit" in command.lower():
            components["topology"] = "basic_circuit"
        
        return components
    except Exception as e:
        print(f"Gemini parsing error: {e}")
        print(f"Raw response: {response.text}")  # Debug print
        # Return default values for basic circuit
        return {"V": 5, "R": 1, "C": 2, "topology": "basic_circuit"}

def open_in_ltspice(circuit_path):
    """
    Open the circuit file in LTspice
    
    Args:
        circuit_path (str): Path to the circuit file
    
    Returns:
        tuple: (success, message)
    """
    try:
        if not os.path.exists(LTSPICE_PATH):
            return False, f"LTspice executable not found at {LTSPICE_PATH}"
            
        if not os.path.exists(circuit_path):
            return False, f"Circuit file not found: {circuit_path}"
            
        # Try to open with shell=True to handle permission issues
        try:
            # Use absolute paths
            abs_ltspice = os.path.abspath(LTSPICE_PATH)
            abs_circuit = os.path.abspath(circuit_path)
            
            # For shortcut files, use the full command string
            if abs_ltspice.endswith('.lnk'):
                subprocess.Popen(f'"{abs_ltspice}" "{abs_circuit}"', shell=True)
            else:
                # For executable files, try both methods
                try:
                    subprocess.Popen([abs_ltspice, abs_circuit], shell=True)
                except Exception:
                    subprocess.Popen(f'"{abs_ltspice}" "{abs_circuit}"', shell=True)
                
            return True, "Circuit opened in LTspice"
        except PermissionError:
            return False, "Permission denied. Please run the script as administrator or check LTspice installation."
        except Exception as e:
            return False, f"Error launching LTspice: {str(e)}"
    except Exception as e:
        return False, f"Error opening LTspice: {str(e)}"

def process_audio(audio_path):
    """
    Process audio file, recognize speech, and create LTspice circuit
    
    Args:
        audio_path (str): Path to audio file
    
    Returns:
        str: Status message
    """
    r = sr.Recognizer()
    temp_files = []

    try:
        # Convert audio file to WAV format
        audio = AudioSegment.from_file(audio_path)
        wav_path = os.path.join(CIRCUIT_DIR, "temp.wav")
        audio.export(wav_path, format="wav")
        temp_files.append(wav_path)

        # Recognize speech
        with sr.AudioFile(wav_path) as source:
            audio_data = r.record(source)
            try:
                # Use Google Speech Recognition
                command = r.recognize_google(audio_data)
                print("You said:", command)

                # Use Gemini to parse command
                components = parse_command_with_gemini_v2(command)
                print("Parsed components:", components)

                # Generate circuit schematic
                schematic_content = generate_circuit_schematic(components)
                
                # Create unique filename with timestamp
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                circuit_filename = f"circuit_{timestamp}.asc"
                circuit_path = os.path.join(CIRCUIT_DIR, circuit_filename)
                
                print(f"Writing circuit to: {circuit_path}")
                print("Circuit content:")
                print(schematic_content)
                
                with open(circuit_path, 'w') as f:
                    f.write(schematic_content)

                # Open the circuit in LTspice
                success, message = open_in_ltspice(circuit_path)
                
                status_message = f"Circuit created successfully!\nRecognized: {command}\nComponents: {components}\nSaved as: {circuit_filename}\n{message}"
                return status_message

            except sr.UnknownValueError:
                return "Could not understand audio"
            except sr.RequestError:
                return "Speech recognition service error"
            except Exception as e:
                return f"Error: {str(e)}"
    finally:
        # Clean up temporary files
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Warning: Could not delete temporary file {file_path}: {str(e)}")

# Gradio Interface
with gr.Blocks() as demo:
    gr.Markdown("# 🎤 Voice-Controlled LTspice Circuit Creator")
    
    with gr.Accordion("About & Instructions", open=False):
        gr.Markdown("""
        ## Voice Commands for Circuit Creation
        
        This tool uses voice commands to create LTspice circuit diagrams. Just describe the circuit you want, and it will be generated automatically.
        
        ### Supported Circuit Types:
        
        1. **Basic Circuit (Default)**:
           - "Basic circuit with 5V, 1 ohm resistor and 2 uF capacitor"
           - "Simple circuit with resistor and capacitor"
           
        2. **Filters**:
           - "RC low pass filter with 1 ohm resistor and 100 microfarad capacitor at 25 kilohertz"
           - "RC high pass filter with 1 ohm resistor and 100 microfarad capacitor at 25 kilohertz"
           - "RC Band Pass Filter": "RC band pass filter with 1 ohm resistors and 100 microfarad capacitors at 25 kilohertz"
           
        ### Tips:
        - Specify component values with units (ohm, k, meg, uF, nF, pF, mH, uH)
        - Mention circuit topology for more accurate results
        - For more complex circuits, try to be specific about connections
        - You can specify frequency for filters (e.g., "at 25 kilohertz")
        - If no specific circuit is recognized, the default Basic Circuit will be created
        """)
    
    # Check LTspice installation at startup
    ltspice_ok, message = check_ltspice_installation()
    if not ltspice_ok:
        gr.Markdown(f"⚠️ {message}")

    with gr.Row():
        with gr.Column():
            audio_input = gr.Audio(sources=["microphone"], type="filepath", label="Record Voice Command")
            text_input = gr.Textbox(label="Or Type Circuit Description", placeholder="e.g., 'RC low pass filter with 10k and 1uF'")
            
    with gr.Row():
        btn_audio = gr.Button("Create Circuit from Audio")
        btn_text = gr.Button("Create Circuit from Text")
    
    with gr.Row():
        text_output = gr.Textbox(label="Status")
    
    with gr.Row():
        gr.Markdown("### Example Circuits")
        
    with gr.Row():
        with gr.Column():
            gr.Markdown("#### Filters")
            filter_examples = [
                gr.Button("Basic Circuit"),
                gr.Button("RC Low Pass Filter"),
                gr.Button("RC High Pass Filter"),
                gr.Button("RC Band Pass Filter")
            ]
        
        
    
    # Function to process text input
    def process_text(text):
        """Process text input to create circuit"""
        try:
            # Use Gemini to parse command
            components = parse_command_with_gemini_v2(text)
            print("Parsed components:", components)

            # Get the topology
            topology = components.get('topology', 'basic_circuit')
            
            # Generate circuit schematic based on topology
            schematic_content = generate_circuit_schematic(components)
            
            # Create unique filename with timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            circuit_filename = f"circuit_{timestamp}.asc"
            circuit_path = os.path.join(CIRCUIT_DIR, circuit_filename)
            
            print(f"Writing circuit to: {circuit_path}")
            
            with open(circuit_path, 'w') as f:
                f.write(schematic_content)

            # Open the circuit in LTspice
            success, message = open_in_ltspice(circuit_path)
            
            status_message = f"Circuit created successfully!\nRecognized: {text}\nTopology: {topology}\nComponents: {components}\nSaved as: {circuit_filename}\n{message}"
            return status_message
        except Exception as e:
            return f"Error: {str(e)}"
    
    # Example circuit descriptions
    examples = {
        "Basic Circuit": "simple circuit with 5V, 1 ohm resistor and 2 uF capacitor",
        "RC Low Pass Filter": "RC low pass filter with 1 ohm resistor and 100 microfarad capacitor at 25 kilohertz",
        "RC High Pass Filter": "RC high pass filter with 1 ohm resistor and 100 microfarad capacitor at 25 kilohertz",
        "RC Band Pass Filter": "RC band pass filter with 1 ohm resistors and 100 microfarad capacitors at 25 kilohertz",
    }
    
    # Connect buttons
    btn_audio.click(fn=process_audio, inputs=audio_input, outputs=text_output)
    btn_text.click(fn=process_text, inputs=text_input, outputs=text_output)
    
    # Connect example buttons
    all_example_buttons = filter_examples
    for btn in all_example_buttons:
        btn_name = btn.value
        if btn_name in examples:
            example_text = examples[btn_name]
            btn.click(
                fn=lambda text=example_text: process_text(text),
                inputs=None,
                outputs=text_output
            )

# Launch the demo
demo.launch() 