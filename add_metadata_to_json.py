import os
import json
import re

json_file = 'schematic_templates.json'

# Load existing templates
with open(json_file, 'r') as f:
    templates = json.load(f)

metadata = {}

for key, lines in templates.items():
    if key == "metadata":
        continue
    params = set()
    for line in lines:
        # Find all {PLACEHOLDER} in the line
        found = re.findall(r'\{([A-Za-z0-9_]+)\}', line)
        params.update(found)
    metadata[key] = sorted(params)

# Insert or update the metadata section
templates["metadata"] = metadata

# Write back to JSON
with open(json_file, 'w') as f:
    json.dump(templates, f, indent=2)

print("Metadata section updated in schematic_templates.json!") 