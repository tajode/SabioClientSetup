#!/usr/bin/env python3
"""
setup_sabio.py

Automates:
1. apt updates & installs (OS packages, drivers)
2. Project folder + Python venv creation
3. Installing Python dependencies
4. Writing /etc/odbc.ini & /etc/odbcinst.ini
5. Scaffolding the sabio-monitor.py script
6. Setting executable permissions
7. Registering the cron job for every-30-min execution
"""

import os
import sys
import subprocess
from pathlib import Path
import getpass
import stat

# --- CONFIGURATION ---
# Adjust these per your environment or externalize to a config file
CRON_SCHEDULE = "*/30 * * * *"
PROJECT_DIR = Path.home() / "sabio-monitor"
VENV_DIR = PROJECT_DIR / "venv"
PYTHON_BIN = VENV_DIR / "bin" / "python"
SCRIPT_PATH = PROJECT_DIR / "sabio-monitor.py"
CRONTAB_MARKER = "# Sábio monitor cron"

ODBC_INI = "/etc/odbc.ini"
ODBCINST_INI = "/etc/odbcinst.ini"

ODBC_INI_CONTENT = """
[MSSQLServer]
Description = Remote SQL Server
Driver = FreeTDS
Server = 161.97.165.126
Port = 1433
Database = test-NetworkMonitoring
TDS_Version = 8.0
""".lstrip()

ODBCINST_INI_CONTENT = """
[FreeTDS]
Description = FreeTDS Driver
Driver = /usr/lib/aarch64-linux-gnu/odbc/libtdsodbc.so
""".lstrip()

PIP_REQUIREMENTS = [
    "speedtest-cli",
    "requests",
    "pandas",
    "sqlalchemy",
    "pyodbc"
]

OS_PACKAGES = [
    "python3-venv",
    "freetds-dev",
    "freetds-bin",
    "unixodbc",
    "tdsodbc"
]

# --- HELPER FUNCTIONS ---

def run(cmd, check=True, **kwargs):
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=check, **kwargs)

def apt_update_and_install():
    run(["apt", "update", "-y"])
    run(["apt", "full-upgrade", "-y"])
    run(["apt", "install", "-y"] + OS_PACKAGES)

def setup_project_folder():
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    os.chdir(PROJECT_DIR)

def create_and_activate_venv():
    run(["python3", "-m", "venv", str(VENV_DIR)])
    # Note: activation is implicit by calling VENV_DIR/bin/python below

def install_python_deps():
    run([str(PYTHON_BIN), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(PYTHON_BIN), "-m", "pip", "install"] + PIP_REQUIREMENTS)

def write_file(path, content, mode=0o644):
    print(f"Writing {path}")
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, mode)

def scaffold_monitor_script():
    if SCRIPT_PATH.exists():
        print(f"{SCRIPT_PATH} already exists; skipping scaffold")
        return
    PAYLOAD = """#!/usr/bin/env python3
import json, subprocess, socket, time
from datetime import datetime
# (…Your sabio-monitor.py content here…)
# Copy your full monitoring script body here.
"""
    write_file(SCRIPT_PATH, PAYLOAD, mode=0o755)

def register_cronjob():
    # Read existing crontab
    result = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    lines = result.stdout.splitlines()
    # Remove old entries
    lines = [l for l in lines if CRONTAB_MARKER not in l]
    # Add new scheduled job
    lines.append(f"{CRON_SCHEDULE} {str(PYTHON_BIN)} {str(SCRIPT_PATH)}  # {CRONTAB_MARKER}")
    # Write back
    cron_content = "\n".join(lines) + "\n"
    p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
    p.communicate(cron_content)
    print("Cron job registered.")

# --- MAIN EXECUTION ---

def main():
    if os.geteuid() != 0:
        print("ERROR: This script must be run as root (sudo).")
        sys.exit(1)

    print("=== Sábio setup automation starting ===")
    apt_update_and_install()                                  # :contentReference[oaicite:0]{index=0}
    setup_project_folder()                                    # :contentReference[oaicite:1]{index=1}
    create_and_activate_venv()                                # :contentReference[oaicite:2]{index=2}
    install_python_deps()                                     # :contentReference[oaicite:3]{index=3}
    write_file(ODBC_INI, ODBC_INI_CONTENT)                    # :contentReference[oaicite:4]{index=4}
    write_file(ODBCINST_INI, ODBCINST_INI_CONTENT)            # :contentReference[oaicite:5]{index=5}
    scaffold_monitor_script()                                 # :contentReference[oaicite:6]{index=6}
    register_cronjob()                                        # :contentReference[oaicite:7]{index=7}

    print("=== Sábio setup automation complete! ===")
    print(f"Device is ready—cron will run the monitor script every 30 minutes.")

if __name__ == "__main__":
    main()
