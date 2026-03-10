import os
import subprocess

LTSPICE_PATH = os.getenv("LTSPICE_PATH", "").strip()


def check_ltspice_installation():
    global LTSPICE_PATH
    if not LTSPICE_PATH or not os.path.exists(LTSPICE_PATH):
        alt_paths = [
            r"C:\\Program Files\\ADI\\LTspice\\LTspice.exe",
            r"C:\\Program Files\\LTC\\LTspiceXVII\\XVIIx64.exe",
            r"C:\\Program Files\\LTspice\\XVII\\XVIIx64.exe",
            r"C:\\Program Files (x86)\\LTspice\\XVII\\XVIIx64.exe",
            r"C:\\Program Files\\LTspice\\XVII\\XVII.exe",
            r"C:\\Program Files (x86)\\LTspice\\XVII\\XVII.exe",
            os.path.join(
                os.path.expanduser("~"),
                "AppData",
                "Roaming",
                "Microsoft",
                "Windows",
                "Start Menu",
                "Programs",
                "LTspice",
                "LTspice.lnk",
            ),
        ]
        for path in alt_paths:
            if os.path.exists(path):
                LTSPICE_PATH = path
                return True, f"LTspice found at {path}"
        return False, "LTspice not found. Please install LTspice or set the LTSPICE_PATH environment variable."
    return True, "LTspice installation found."


def open_in_ltspice(circuit_path):
    try:
        if not os.path.exists(LTSPICE_PATH):
            return False, f"LTspice executable not found at {LTSPICE_PATH}"
        if not os.path.exists(circuit_path):
            return False, f"Circuit file not found: {circuit_path}"

        abs_ltspice = os.path.abspath(LTSPICE_PATH)
        abs_circuit = os.path.abspath(circuit_path)

        if abs_ltspice.endswith(".lnk"):
            subprocess.Popen(f'"{abs_ltspice}" "{abs_circuit}"', shell=True)
        else:
            try:
                subprocess.Popen([abs_ltspice, abs_circuit], shell=True)
            except Exception:
                subprocess.Popen(f'"{abs_ltspice}" "{abs_circuit}"', shell=True)
        return True, "Circuit opened in LTspice"
    except PermissionError:
        return False, "Permission denied. Please run the script as administrator or check LTspice installation."
    except Exception as exc:
        return False, f"Error opening LTspice: {exc}"
