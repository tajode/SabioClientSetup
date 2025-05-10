# -------------------------------------------------------------------------
# Network Performance Monitor for Project Savio
# -------------------------------------------------------------------------
# This script measures internet connectivity and performance metrics for
# school GPON connections, storing results in a centralized database.
#
# Configuration parameters that should be moved to a config file:
# - AGENT_VERSION: Current script version (1.0.0)
# - CONTRACTED_DOWNLOAD_MBPS: Expected download speed from ISP (100.0)
# - CONTRACTED_UPLOAD_MBPS: Expected upload speed from ISP (20.0)
# - Ping parameters: Target host (8.8.8.8), retry count (3), delay (2s)
# - Speed test parameters: Retry count (3), delay between retries (3s)
# - SLA threshold: Currently 80% of contracted speeds
# - Geolocation API: URL and timeout settings
# - Database connection: Credentials, host, port, database name
# -------------------------------------------------------------------------

import speedtest
import requests
import socket
import subprocess
import json
import time
import platform
import os
import re
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote_plus

# Constants
# TODO: Move all configuration constants to external config file
AGENT_VERSION = "1.0.0"
# These would typically come from a config file
CONTRACTED_DOWNLOAD_MBPS = 100.0
CONTRACTED_UPLOAD_MBPS = 20.0

# -------------------------
# Get the hostname of the device (used as unique identifier)
# -------------------------
def get_hostname():
    return socket.gethostname()

# -------------------------
# Extract school name from hostname (assuming format KE-<CountyCode>-SCH-<SchoolCode>-SPEED1)
# -------------------------
def get_school_name():
    hostname = get_hostname()
    # If hostname follows the expected pattern, extract school code
    match = re.match(r"KE-[A-Z]+-SCH-([A-Z0-9]+)-SPEED\d+", hostname)
    if match:
        return f"School-{match.group(1)}"
    return hostname  # Fallback to hostname if pattern doesn't match

# -------------------------
# Get OS version information
# -------------------------
def get_os_version():
    return f"{platform.system()} {platform.release()} ({platform.version()})"

# -------------------------
# Get device uptime in seconds
# -------------------------
def get_uptime_seconds():
    try:
        if platform.system() == "Linux":
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
            return int(uptime_seconds)
        elif platform.system() == "Darwin":  # macOS
            cmd = "sysctl -n kern.boottime | awk '{print $4}' | sed 's/,//'"
            boot_time = int(subprocess.check_output(cmd, shell=True).decode().strip())
            uptime_seconds = int(time.time() - boot_time)
            return uptime_seconds
        elif platform.system() == "Windows":
            uptime_seconds = int(subprocess.check_output("powershell (Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime | Select-Object -ExpandProperty TotalSeconds", shell=True).decode().strip())
            return uptime_seconds
    except Exception:
        return 0  # Return 0 if uptime cannot be determined
    return 0

# -------------------------
# Try to ping a public host up to 3 times to verify internet reachability
# -------------------------
def check_ping(host="8.8.8.8", retries=3, delay=2):
    # TODO: Move ping configuration parameters to config file
    packet_loss = 100.0  # Default to 100% loss
    
    for attempt in range(retries):
        try:
            if platform.system() == "Windows":
                ping_output = subprocess.check_output(["ping", "-n", "5", host], timeout=10, universal_newlines=True)
                match = re.search(r"Lost = (\d+)", ping_output)
                if match:
                    lost_packets = int(match.group(1))
                    packet_loss = (lost_packets / 5) * 100
            else:  # Linux/macOS
                ping_output = subprocess.check_output(["ping", "-c", "5", host], timeout=10, universal_newlines=True)
                match = re.search(r"(\d+)% packet loss", ping_output)
                if match:
                    packet_loss = float(match.group(1))
            
            return True, packet_loss
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt < retries - 1:
                time.sleep(delay)
    
    return False, packet_loss

# -------------------------
# Try to run a speed test up to 3 times before failing
# -------------------------
def run_speed_test(retries=3, delay=3):
    # TODO: Move speed test configuration parameters to config file
    for attempt in range(retries):
        try:
            start_time = time.time()
            
            st = speedtest.Speedtest()
            server = st.get_best_server()
            
            download = st.download() / 1_000_000  # Convert from bps to Mbps
            upload = st.upload() / 1_000_000      # Convert from bps to Mbps
            ping = st.results.ping
            ip = st.results.client['ip']
            
            # Get jitter - many speedtest implementations don't include this
            # If not available in your speedtest library, you might need a different approach
            jitter = getattr(st.results, 'jitter', 0.0)
            
            end_time = time.time()
            test_duration = end_time - start_time
            
            return {
                "download_mbps": download,
                "upload_mbps": upload,
                "ping_ms": ping,
                "ip": ip,
                "jitter_ms": jitter,
                "test_duration_sec": test_duration,
                "test_server": server['name'],
                "test_server_ip": server['host']
            }
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise Exception(f"Speed test failed after {retries} attempts: {str(e)}")


# -------------------------
# Fetch approximate geolocation based on public IP using ipinfo.io
# -------------------------
def get_location():
    # TODO: Move geolocation API URL and timeout to config file
    try:
        response = requests.get("https://ipinfo.io/json", timeout=5)
        data = response.json()
        lat, lon = (0.0, 0.0)
        if "loc" in data:
            loc = data["loc"].split(",")
            lat, lon = float(loc[0]), float(loc[1])
        return {
            "latitude": lat,
            "longitude": lon,
            "city": data.get("city", ""),
            "region": data.get("region", ""),
            "org": data.get("org", "")
        }
    except Exception:
        return {
            "latitude": 0.0,
            "longitude": 0.0,
            "city": "",
            "region": "",
            "org": ""
        }

# -------------------------
# Calculate SLA compliance metrics
# -------------------------
def calculate_sla_metrics(download_mbps, upload_mbps):
    # TODO: Move SLA threshold parameters to config file
    # Calculate percentage of contracted speeds
    download_percentage = (download_mbps / CONTRACTED_DOWNLOAD_MBPS) * 100 if CONTRACTED_DOWNLOAD_MBPS > 0 else 0
    upload_percentage = (upload_mbps / CONTRACTED_UPLOAD_MBPS) * 100 if CONTRACTED_UPLOAD_MBPS > 0 else 0
    
    # SLA is compliant if both download and upload are at least 80% of contracted speeds
    # TODO: Extract SLA threshold (80%) to config file
    is_compliant = download_percentage >= 80 and upload_percentage >= 80
    
    # Deviation percentage (negative values indicate underperformance)
    download_deviation = download_percentage - 100
    upload_deviation = upload_percentage - 100
    # Use the worse of the two deviations
    sla_deviation = min(download_deviation, upload_deviation)
    
    return {
        "contracted_download_mbps": CONTRACTED_DOWNLOAD_MBPS,
        "contracted_upload_mbps": CONTRACTED_UPLOAD_MBPS,
        "sla_compliance": is_compliant,
        "sla_deviation_pct": sla_deviation
    }

# -------------------------
# Main function: orchestrates the full monitoring process
# -------------------------
def main():
    start_time = time.time()
    error_code = 0  # 0 = No error
    error_message = ""

    # Initialize result dictionary
    result = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "device_id": get_hostname(),
        "school_name": get_school_name(),
        "agent_version": AGENT_VERSION,
        "os_version": get_os_version(),
        "device_uptime_sec": get_uptime_seconds()
    }

    # Check internet connectivity
    ping_success, packet_loss = check_ping()
    result["ping_success"] = ping_success
    result["packet_loss_pct"] = packet_loss

    if not ping_success:
        result.update({
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "ping_ms": None,
            "jitter_ms": None,
            "test_duration_sec": 0.0,
            "test_server": "",
            "test_server_ip": "",
            "ip": "Unavailable",
            "error_code": 1,  # 1 = No internet connection
            "error_message": "No internet connection"
        })
    else:
        try:
            # Run speed test
            speed_data = run_speed_test()
            result.update(speed_data)
            
            # Round numeric values for readability
            for key in ["download_mbps", "upload_mbps", "ping_ms", "jitter_ms", "test_duration_sec"]:
                if key in result and result[key] is not None:
                    result[key] = round(result[key], 2)
            
            # Calculate SLA metrics
            sla_data = calculate_sla_metrics(result["download_mbps"], result["upload_mbps"])
            result.update(sla_data)
            
        except Exception as e:
            result.update({
                "download_mbps": 0.0,
                "upload_mbps": 0.0,
                "ping_ms": None,
                "jitter_ms": None,
                "test_duration_sec": 0.0,
                "test_server": "",
                "test_server_ip": "",
                "ip": "Unavailable",
                "error_code": 2,  # 2 = Speed test failed
                "error_message": f"Speed test failed: {str(e)}"
            })

    # Get geolocation data
    geo_data = get_location()
    result.update(geo_data)

    # Output to console
    print(json.dumps(result, indent=2))

    # Convert ISO timestamp to datetime object
    timestamp_dt = datetime.fromisoformat(result["timestamp"].replace("Z", ""))

    # Prepare DataFrame for insert
    df = pd.DataFrame([{
        "TimestampUtc": timestamp_dt,
        "DeviceId": str(result["device_id"]),
        "SchoolName": str(result["school_name"]),
        "AgentVersion": str(result["agent_version"]),
        "OsVersion": str(result["os_version"]),
        "DeviceUptimeSec": int(result["device_uptime_sec"]),
        "PingSuccess": bool(result["ping_success"]),
        "DownloadMbps": float(result["download_mbps"]),
        "UploadMbps": float(result["upload_mbps"]),
        "PingMs": float(result["ping_ms"]) if result["ping_ms"] is not None else None,
        "JitterMs": float(result["jitter_ms"]) if "jitter_ms" in result and result["jitter_ms"] is not None else None,
        "PacketLossPct": float(result["packet_loss_pct"]),
        "TestDurationSec": float(result["test_duration_sec"]) if "test_duration_sec" in result else 0.0,
        "TestServer": str(result["test_server"]) if "test_server" in result else "",
        "TestServerIp": str(result["test_server_ip"]) if "test_server_ip" in result else "",
        "ContractedDownloadMbps": float(result.get("contracted_download_mbps", 0.0)),
        "ContractedUploadMbps": float(result.get("contracted_upload_mbps", 0.0)),
        "SlaCompliance": bool(result.get("sla_compliance", False)),
        "SlaDeviationPct": float(result.get("sla_deviation_pct", 0.0)),
        "IpAddress": str(result["ip"]) if "ip" in result else "",
        "Latitude": float(result["latitude"]),
        "Longitude": float(result["longitude"]),
        "City": str(result["city"]),
        "Region": str(result["region"]),
        "ISPName": str(result["org"]),
        "ErrorCode": int(result.get("error_code", 0)),
        "ErrorMessage": str(result.get("error_message", ""))
    }])

    # Define SQLAlchemy engine
    try:
        # TODO: Move database connection details to config file or secure credential store
        password = quote_plus("This@1sAwful")
        conn_str = (
            f"mssql+pyodbc://sa:{password}@161.97.165.126:1433/aspnet-SabioMonitoring"
            "?driver=FreeTDS&charset=utf8&TDS_Version=8.0"
        )
        engine = create_engine(conn_str)

        # Insert the record
        df.to_sql(
            name="NetworkTestResults",
            con=engine,
            schema="dbo",
            if_exists="append",
            index=False
        )
        print(" Data inserted into SQL Server.")

    except Exception as e:
        print(f" Database insert error: {e}")

    # Show total script execution time
    duration = round(time.time() - start_time, 2)
    print(f"\nExecution time: {duration} seconds")

# -------------------------
# Entry point
# -------------------------
if __name__ == "__main__":
    main()
