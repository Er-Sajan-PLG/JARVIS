# app/utils/server_manager.py
import socket
import subprocess
import time
import sys

def is_port_open(port: int) -> bool:
    """Check if a port is already listening"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('localhost', port)) == 0

def ensure_server_running(port: int, command: list[str], name: str = "LLM"):
    """
    Check if a server is running on a port. If not, start it.
    Waits until the port is open before returning.
    """
    if is_port_open(port):
        print(f"✅ {name} already running on port {port}")
        return

    print(f"⏳ {name} not found on port {port}. Starting in background...")
    
    # Start process in background, suppress output
    subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Wait for it to be ready (max 30 seconds)
    for i in range(30):
        time.sleep(1)
        if is_port_open(port):
            print(f"✅ {name} started successfully on port {port}")
            return
        print(f"   Waiting for {name} to boot... ({i+1}s)")

    print(f"❌ Failed to start {name} after 30 seconds.")
    sys.exit(1)