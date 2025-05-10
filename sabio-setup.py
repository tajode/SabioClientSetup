#!/usr/bin/env python3
"""
setup_sabio.py

Automates:
1. apt updates & installs (OS packages, drivers)
2. Git clone of the SabioClientSetup repository
3. Python venv creation and dependency installation
4. Writing /etc/odbc.ini & /etc/odbcinst.ini
5. Registering the cron job for periodic execution of sabio-monitor.py
"""

import os
import sys
import subprocess
from pathlib import Path
from textwrap import dedent

# --- CONFIGURATION ---
REPO_URL = "https://github.com/tajode/SabioClientSetup.git"
PROJECT_DIR = Path.home() / "SabioClientSetup"
VENV_DIR = PROJECT_DIR / "venv"
PYTHON_BIN = VENV_DIR / "bin" / "python"
MONITOR_SCRIPT = PROJECT_DIR / "sabio-monitor.py"
CRON_MARKER = "# sabio-monitor cron"
CRON_SCHEDULE = "*/30 * * * *"

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


def clone_repo():
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    if (PROJECT_DIR / ".git").exists():
        print("Repository already exists, pulling latest changes.")
        run(["git", "-C", str(PROJECT_DIR), "pull"])
    else:
        run(["git", "clone", REPO_URL, str(PROJECT_DIR)])


def create_and_install_venv():
    if not VENV_DIR.exists():
        run(["python3", "-m", "venv", str(VENV_DIR)])
    pip = VENV_DIR / "bin" / "pip"
    run([str(pip), "install", "--upgrade", "pip"])
    req_file = PROJECT_DIR / "requirements.txt"
    if req_file.exists():
        run([str(pip), "install", "-r", str(req_file)])
    else:
        # Fallback packages
        run([str(pip), "install", "speedtest-cli", "requests", "pandas", "sqlalchemy", "pyodbc"])


def write_config(path, content):
    print(f"Writing {path}")
    with open(path, 'w') as f:
        f.write(content)


def configure_odbc():
    write_config(ODBC_INI,    ODBC_INI_CONTENT)
    write_config(ODBCINST_INI, ODBCINST_INI_CONTENT)


def register_cron():
    cron_line = f"{CRON_SCHEDULE} {PYTHON_BIN} {MONITOR_SCRIPT} {CRON_MARKER}"
    # load existing crontab
    result = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    lines = [l for l in result.stdout.splitlines() if CRON_MARKER not in l]
    lines.append(cron_line)
    cron_text = "\n".join(lines) + "\n"
    p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
    p.communicate(cron_text)
    print("Cron job registered.")


# --- MAIN ---
def main():
    if os.geteuid() != 0:
        sys.exit("Error: run this script with sudo or as root.")

    print("=== Starting SabioClientSetup automation ===")
    apt_install()
    clone_repo()
    create_and_install_venv()
    configure_odbc()

    # Ensure monitor script is executable
    if MONITOR_SCRIPT.exists():
        MONITOR_SCRIPT.chmod(0o755)
    else:
        print(f"Warning: {MONITOR_SCRIPT} not found.")

    register_cron()

    print("=== Setup complete! sabio-monitor will run every 30 minutes ===")


if __name__ == '__main__':
    main()
