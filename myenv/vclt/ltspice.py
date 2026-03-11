import os
import subprocess
import sys

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
        # Ensure circuit exists early so macOS branch can use it without LTSPICE_PATH
        if not os.path.exists(circuit_path):
            return False, f"Circuit file not found: {circuit_path}"

        abs_circuit = os.path.abspath(circuit_path)

        # macOS: try multiple ways to open LTspice and capture results for debugging
        if sys.platform == "darwin":
            attempts = []

            def try_cmd(cmd):
                try:
                    cp = subprocess.run(cmd, capture_output=True, text=True)
                    attempts.append((cmd, cp.returncode, cp.stdout.strip(), cp.stderr.strip()))
                    return cp.returncode == 0
                except Exception as exc:
                    attempts.append((cmd, None, "", str(exc)))
                    return False

            # 1) open by app name
            if try_cmd(["open", "-a", "LTspice", abs_circuit]):
                return True, "Circuit opened in LTspice (macOS)"

            # 2) open by absolute app path
            app_path = "/Applications/LTspice.app"
            if os.path.exists(app_path) and try_cmd(["open", "-a", app_path, abs_circuit]):
                return True, "Circuit opened in LTspice (macOS, app path)"

            # 3) direct binary inside app bundle
            app_exec = "/Applications/LTspice.app/Contents/MacOS/LTspice"
            if os.path.exists(app_exec) and try_cmd([app_exec, abs_circuit]):
                return True, "Circuit opened in LTspice (macOS, binary)"

            # 4) open with --args (some apps expect args)
            if try_cmd(["open", "-a", "LTspice", "--args", abs_circuit]):
                return True, "Circuit opened in LTspice (macOS, with --args)"

            # If none succeeded, return diagnostics
            details = []
            for cmd, rc, out, err in attempts:
                details.append(f"cmd={cmd} rc={rc} out={out!r} err={err!r}")
            return False, "Failed to open LTspice on macOS. Attempts:\n" + "\n".join(details)

        if not os.path.exists(LTSPICE_PATH):
            return False, f"LTspice executable not found at {LTSPICE_PATH}"

        abs_ltspice = os.path.abspath(LTSPICE_PATH)

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
