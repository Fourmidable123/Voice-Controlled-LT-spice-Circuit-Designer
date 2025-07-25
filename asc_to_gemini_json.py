import os
import json
import google.generativeai as genai

# Set your Gemini API key here
GEMINI_API_KEY = 'AIzaSyBaOcBLjW-R2jSk_1HulsYGHjiaYCGu_mU'
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')  # or 'gemini-1.0-pro' if you have access

asc_dir = './asc files'  # Directory with .asc files
json_file = 'schematic_templates.json'

# Load existing templates if the file exists
if os.path.exists(json_file):
    with open(json_file, 'r') as f:
        templates = json.load(f)
else:
    templates = {}

print(f"Looking for .asc files in: {os.path.abspath(asc_dir)}")
asc_files = [f for f in os.listdir(asc_dir) if f.lower().endswith('.asc')]
if not asc_files:
    print("No .asc files found.")
else:
    print(f"Found {len(asc_files)} .asc files: {asc_files}")

for idx, filename in enumerate(asc_files, 1):
    print(f"Processing file {idx} of {len(asc_files)}: {filename}")
    key = os.path.splitext(filename)[0].replace('-', '_').replace(' ', '_').lower()
    with open(os.path.join(asc_dir, filename), 'r') as f:
        netlist = f.read()
    prompt = f"""
Given the following LTspice netlist, replace all component values (resistors, capacitors, voltages, inductors, etc.) with placeholders in curly braces, using the instance name as the placeholder (e.g., {{R1}}, {{C2}}, {{Vd}}, {{L1}}).
Return the modified netlist as a JSON array of strings, one per line, suitable for inclusion in a JSON file.

Netlist:
{netlist}
"""
    try:
        response = model.generate_content(prompt)
        text = response.text
        start = text.find('[')
        end = text.rfind(']')
        if start == -1 or end == -1:
            raise ValueError("No JSON array found in Gemini response.")
        json_array = text[start:end+1]
        lines = json.loads(json_array)
        templates[key] = lines
        print(f"Processed {filename} -> {key}")
    except Exception as e:
        print(f"Error processing {filename}: {e}")

# Write back to JSON
with open(json_file, 'w') as f:
    json.dump(templates, f, indent=2)

print(f"Added {len(templates)} templates to {json_file} with Gemini-generated placeholders.") 

import subprocess
subprocess.run(['python', 'add_metadata_to_json.py']) 