#!/usr/bin/env python3
"""
setup_sabio.py

Automates the setup of the Sabio monitoring agent:
1. apt updates & installs (OS packages, drivers)
2. Python venv creation and dependency installation
3. Writing /etc/odbc.ini & /etc/odbcinst.ini
4. Registering the cron job for periodic execution of sabio-monitor.py

This script guides you through the entire process with clear explanations.
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
    print("\n=== STEP 1: Updating system packages ===")
    print("Updating package lists from repositories...")
    run(["apt", "update", "-y"])
    
    print("\nUpgrading existing packages to latest versions...")
    print("This may take several minutes depending on your connection speed.")
    run(["apt", "full-upgrade", "-y"])
    
    print("\nInstalling required packages:")
    for pkg in OS_PACKAGES:
        print(f"  - {pkg}")
    run(["apt", "install", "-y"] + OS_PACKAGES)
    print("✓ System packages installation complete")


def create_project_dir():
    print("\n=== STEP 2: Creating project directory ===")
    print(f"Creating directory structure at {PROJECT_DIR}")
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Project directory created at {PROJECT_DIR}")


def create_and_install_venv():
    print("\n=== STEP 3: Setting up Python virtual environment ===")
    
    if not VENV_DIR.exists():
        print(f"Creating new virtual environment at {VENV_DIR}")
        run(["python3", "-m", "venv", str(VENV_DIR)])
    else:
        print(f"Using existing virtual environment at {VENV_DIR}")
    
    pip = VENV_DIR / "bin" / "pip"
    print("\nUpdating pip to latest version...")
    run([str(pip), "install", "--upgrade", "pip"])
    
    print("\nInstalling required Python packages:")
    print("  - speedtest-cli: for network speed testing")
    print("  - requests: for HTTP API communication")
    print("  - pandas: for data manipulation")
    print("  - sqlalchemy: for database operations")
    print("  - pyodbc: for ODBC database connections")
    print("\nThis may take several minutes...")
    run([str(pip), "install", "speedtest-cli", "requests", "pandas", "sqlalchemy", "pyodbc"])
    print("✓ Python virtual environment setup complete")


def write_config(path, content):
    print(f"Writing configuration to {path}")
    with open(path, 'w') as f:
        f.write(content)


def configure_odbc():
    print("\n=== STEP 4: Configuring ODBC database connection ===")
    print("Setting up connection to SQL Server database for storing monitoring data")
    
    print(f"\nCreating ODBC Data Source configuration at {ODBC_INI}")
    print("This defines the connection to the remote SQL Server database")
    write_config(ODBC_INI, ODBC_INI_CONTENT)
    
    print(f"\nCreating ODBC Driver configuration at {ODBCINST_INI}")
    print("This defines the FreeTDS driver used to connect to SQL Server")
    write_config(ODBCINST_INI, ODBCINST_INI_CONTENT)
    
    print("✓ ODBC configuration complete")


def register_cron():
    print("\n=== STEP 5: Setting up automated monitoring ===")
    print("Configuring cron job to run the monitoring script every 2 minutes")
    
    # Use absolute paths for the cron job as in the documentation
    abs_python_path = str(Path.home() / "sabio-monitor/sabio-venv/bin/python")
    abs_script_path = str(Path.home() / "sabio-monitor/sabio-monitor.py")
    cron_line = f"{CRON_SCHEDULE} {abs_python_path} {abs_script_path} {CRON_MARKER}"
    
    print(f"Cron schedule: {CRON_SCHEDULE} (every 2 minutes)")
    print(f"Using Python interpreter: {abs_python_path}")
    print(f"Running script: {abs_script_path}")
    
    # load existing crontab
    result = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    lines = [l for l in result.stdout.splitlines() if CRON_MARKER not in l]
    lines.append(cron_line)
    cron_text = "\n".join(lines) + "\n"
    
    print("Updating crontab...")
    p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
    p.communicate(cron_text)
    print("✓ Cron job successfully registered")


# --- MAIN ---
def main():
    print("\n======================================================")
    print("         SABIO MONITORING AGENT SETUP UTILITY")
    print("======================================================\n")
    
    if os.geteuid() != 0:
        sys.exit("Error: This script must be run with sudo or as root user.")

    print("This utility will set up the Sabio monitoring agent on your Raspberry Pi.")
    print("It will guide you through the entire installation process.")
    print("Follow the prompts to complete the setup.\n")
    
    try:
        apt_install()
        create_project_dir()
        create_and_install_venv()
        configure_odbc()

        # Create a placeholder monitor script if it doesn't exist
        print("\n=== STEP 6: Creating monitoring script ===")
        if not MONITOR_SCRIPT.exists():
            print(f"Creating initial monitoring script at {MONITOR_SCRIPT}")
            with open(MONITOR_SCRIPT, 'w') as f:
                f.write('#!/usr/bin/env python3\n')
                f.write('# Sabio monitoring script\n')
                f.write('# Update this file with the actual monitoring code\n')
            print("✓ Initial script created")
        else:
            print(f"Found existing monitoring script at {MONITOR_SCRIPT}")
        
        # Ensure monitor script is executable
        print("Making script executable...")
        MONITOR_SCRIPT.chmod(0o755)
        print("✓ Script permissions set")

        register_cron()

        print("\n======================================================")
        print("               SETUP COMPLETE SUCCESSFULLY")
        print("======================================================\n")
        
        print("Your Sabio monitoring agent has been configured with:")
        print(f"  - Project directory: {PROJECT_DIR}")
        print(f"  - Virtual environment: {VENV_DIR}")
        print(f"  - Monitor script: {MONITOR_SCRIPT}")
        print(f"  - Monitoring frequency: Every 2 minutes")
        print("\nThe monitoring agent will start collecting data automatically.")
        print("No further action is required.")
        
    except Exception as e:
        print(f"\n❌ ERROR: Setup failed: {str(e)}")
        print("Please fix the error and try running the script again.")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
