import speech_recognition as sr
import os
import google.generativeai as genai
from pydub import AudioSegment
import gradio as gr
import time
import subprocess

# Configure Gemini API
GEMINI_API_KEY = 'AIzaSyCUNr2gW0CARK1LwI20rzfAjcpuPzHyUc0'
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
    
    Returns:
        str: LTspice schematic content
    """
    # Create a basic schematic with proper LTspice syntax
    schematic = []
    
    # Add LTspice schematic header
    schematic.append("Version 4")
    schematic.append("SHEET 1 880 680")
    
    # Starting position for components
    x_start = 96
    y_start = 96
    spacing = 128  # Horizontal spacing between components
    
    # Add voltage source
    schematic.append(f"SYMBOL voltage {x_start} {y_start} R0")
    schematic.append("WINDOW 123 0 0 Left 0")
    schematic.append("WINDOW 39 0 0 Left 0")
    schematic.append("SYMATTR InstName V1")
    schematic.append("SYMATTR Value SINE(0 1 1000)")
    
    # Current position tracking
    x_pos = x_start + spacing
    last_x = x_start
    
    # Add components in series
    if 'R' in components:
        # Add resistor
        schematic.append(f"SYMBOL res {x_pos} {y_start} R0")
        schematic.append("WINDOW 0 32 32 Left 2")
        schematic.append("WINDOW 3 32 68 Left 2")
        schematic.append("SYMATTR InstName R1")
        schematic.append(f"SYMATTR Value {components['R']}")
        last_x = x_pos
        x_pos += spacing
    
    if 'C' in components:
        # Add capacitor
        schematic.append(f"SYMBOL cap {x_pos} {y_start} R0")
        schematic.append("WINDOW 0 32 32 Left 2")
        schematic.append("WINDOW 3 32 68 Left 2")
        schematic.append("SYMATTR InstName C1")
        schematic.append(f"SYMATTR Value {components['C']}")
        last_x = x_pos
        x_pos += spacing
    
    if 'L' in components:
        # Add inductor
        schematic.append(f"SYMBOL ind {x_pos} {y_start} R0")
        schematic.append("WINDOW 0 32 32 Left 2")
        schematic.append("WINDOW 3 32 68 Left 2")
        schematic.append("SYMATTR InstName L1")
        schematic.append(f"SYMATTR Value {components['L']}")
        last_x = x_pos
        x_pos += spacing
    
    # Add ground symbol
    ground_x = x_start
    ground_y = y_start + 96
    schematic.append(f"FLAG {ground_x} {ground_y} 0")
    
    # Add wires to connect components
    schematic.append(f"WIRE {x_start} {y_start} {x_start + spacing} {y_start}")
    
    # Wire between components
    if last_x > x_start + spacing:
        schematic.append(f"WIRE {x_start + spacing} {y_start} {last_x} {y_start}")
    
    # Wire from voltage source negative to ground
    schematic.append(f"WIRE {x_start} {y_start + 64} {x_start} {ground_y}")
    
    # Wire from last component to ground
    schematic.append(f"WIRE {last_x} {y_start} {last_x} {ground_y}")
    schematic.append(f"WIRE {x_start} {ground_y} {last_x} {ground_y}")
    
    # Add simulation command
    schematic.append("TEXT -64 240 Left 2 !.tran 0 1ms 0")
    
    return '\n'.join(schematic)

def parse_command_with_gemini(command):
    """
    Use Gemini to parse circuit parameters from speech command
    
    Args:
        command (str): Recognized speech command
    
    Returns:
        dict: Component specifications
    """
    prompt = '''
    Extract circuit component values from this command: '{}'
    
    Rules:
    - If no value specified, use default (1000 ohms, 1e-6 farads)
    - Return ONLY a Python dictionary with component values
    - Interpret common units (k, m, u, n)
    - Include any additional components mentioned
    - Include component tolerances if specified
    - Include component types if specified (e.g., ceramic, electrolytic)
    - Do not include any explanations or markdown formatting
    - Format numbers using scientific notation (e.g., 1e3 for 1k)
    
    Examples:
    "1k ohm and 1 microfarad" -> {{"R": 1e3, "C": 1e-6}}
    "two thousand ohms and 2 millihenry" -> {{"R": 2e3, "L": 2e-3}}
    "default settings" -> {{"R": 1e3, "C": 1e-6}}
    "100 ohm resistor and 0.1uF ceramic capacitor" -> {{"R": 100, "C": 1e-7, "C_type": "ceramic"}}
    
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
        
        # Ensure values are numeric
        for key, value in components.items():
            if key not in ['C_type', 'R_type', 'L_type'] and not isinstance(value, (int, float)):
                raise ValueError(f"Invalid value for {key}: {value}")
        
        return components
    except Exception as e:
        print(f"Gemini parsing error: {e}")
        print(f"Raw response: {response.text}")  # Debug print
        # Return default values with proper scientific notation
        return {"R": 1e3, "C": 1e-6}  # Default values

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
                components = parse_command_with_gemini(command)
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
    gr.Markdown("Record your command (e.g., '1k ohm and 1 microfarad')")
    
    # Check LTspice installation at startup
    ltspice_ok, message = check_ltspice_installation()
    if not ltspice_ok:
        gr.Markdown(f"⚠️ {message}")

    with gr.Row():
        audio_input = gr.Audio(sources=["microphone"], type="filepath")
        btn = gr.Button("Create Circuit")

    text_output = gr.Textbox()

    btn.click(
        fn=process_audio,
        inputs=audio_input,
        outputs=text_output
    )

# Launch the demo
demo.launch() 