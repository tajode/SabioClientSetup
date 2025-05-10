#!/usr/bin/env python3
"""
setup_sabio.py

Automates:
1. apt updates & installs (OS packages, drivers)
2. Python venv creation and dependency installation
3. Writing /etc/odbc.ini & /etc/odbcinst.ini
4. Registering the cron job for periodic execution of sabio-monitor.py
"""

import os
import sys
import subprocess
from pathlib import Path
from textwrap import dedent

# --- CONFIGURATION ---
PROJECT_DIR = Path.home() / "sabio-monitor"
VENV_DIR = PROJECT_DIR / "sabio-venv"
PYTHON_BIN = VENV_DIR / "bin" / "python"
MONITOR_SCRIPT = PROJECT_DIR / "sabio-monitor.py"
CRON_MARKER = "# sabio-monitor cron"
CRON_SCHEDULE = "*/2 * * * *"  # Run every 2 minutes per documentation

OS_PACKAGES = [
    "git", "python3-venv",
    "freetds-dev", "freetds-bin", "unixodbc", "tdsodbc"
]

ODBC_INI = "/etc/odbc.ini"
ODBCINST_INI = "/etc/odbcinst.ini"
ODBC_INI_CONTENT = dedent("""
[MSSQLServer]
Description = Remote SQL Server
Driver      = FreeTDS
Server      = 161.97.165.126
Port        = 1433
Database    = test-NetworkMonitoring
TDS_Version = 8.0
""")
ODBCINST_INI_CONTENT = dedent("""
[FreeTDS]
Description = FreeTDS Driver
Driver      = /usr/lib/aarch64-linux-gnu/odbc/libtdsodbc.so
""")

# --- HELPER FUNCTIONS ---
def run(cmd):
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def apt_install():
    run(["apt", "update", "-y"])
    run(["apt", "full-upgrade", "-y"])
    run(["apt", "install", "-y"] + OS_PACKAGES)


def create_project_dir():
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Created project directory at {PROJECT_DIR}")


def create_and_install_venv():
    if not VENV_DIR.exists():
        run(["python3", "-m", "venv", str(VENV_DIR)])
    pip = VENV_DIR / "bin" / "pip"
    run([str(pip), "install", "--upgrade", "pip"])
    # Install required packages directly as specified in documentation
    run([str(pip), "install", "speedtest-cli", "requests", "pandas", "sqlalchemy", "pyodbc"])


def write_config(path, content):
    print(f"Writing {path}")
    with open(path, 'w') as f:
        f.write(content)


def configure_odbc():
    write_config(ODBC_INI, ODBC_INI_CONTENT)
    write_config(ODBCINST_INI, ODBCINST_INI_CONTENT)


def register_cron():
    # Use absolute paths for the cron job as in the documentation
    abs_python_path = str(Path.home() / "sabio-monitor/sabio-venv/bin/python")
    abs_script_path = str(Path.home() / "sabio-monitor/sabio-monitor.py")
    cron_line = f"{CRON_SCHEDULE} {abs_python_path} {abs_script_path} {CRON_MARKER}"
    
    # load existing crontab
    result = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    lines = [l for l in result.stdout.splitlines() if CRON_MARKER not in l]
    lines.append(cron_line)
    cron_text = "\n".join(lines) + "\n"
    p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
    p.communicate(cron_text)
    print("Cron job registered to run every 2 minutes.")


# --- MAIN ---
def main():
    if os.geteuid() != 0:
        sys.exit("Error: run this script with sudo or as root.")

    print("=== Starting Sabio monitoring setup automation ===")
    apt_install()
    create_project_dir()
    create_and_install_venv()
    configure_odbc()

    # Create a placeholder monitor script if it doesn't exist
    if not MONITOR_SCRIPT.exists():
        print(f"Creating placeholder {MONITOR_SCRIPT}")
        with open(MONITOR_SCRIPT, 'w') as f:
            f.write('#!/usr/bin/env python3\n')
            f.write('# Sabio monitoring script\n')
            f.write('# Update this file with the actual monitoring code\n')
    
    # Ensure monitor script is executable
    MONITOR_SCRIPT.chmod(0o755)

    register_cron()

    print("=== Setup complete! sabio-monitor will run every 2 minutes ===")
    print(f"Project directory: {PROJECT_DIR}")
    print(f"Virtual environment: {VENV_DIR}")
    print(f"Monitor script: {MONITOR_SCRIPT}")


if __name__ == '__main__':
    main()
