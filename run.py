#!/usr/bin/env python3
"""
PDF Knowledge Base System Startup Script

This script is used to start the PDF Knowledge Base System from the project root directory.
The frontend static files should already be built and placed in the backend/static directory.
"""

import os
import sys
import subprocess
import time

def check_requirements():
    """Check project dependencies and environment"""
    print("Checking project environment...")
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("Error: Python 3.8 or higher is required")
        sys.exit(1)
    
    # Check static files directory
    if not os.path.exists("backend/static"):
        print("Error: Static files directory not found, please ensure frontend is built")
        sys.exit(1)
    
    # Check if index.html exists
    if not os.path.exists("backend/static/index.html"):
        print("Error: index.html is missing in static files directory")
        sys.exit(1)
    
    print("Environment check passed!")

def start_server():
    """Start FastAPI server"""
    print("Starting PDF Knowledge Base System...")
    
    # Change to backend directory
    os.chdir("backend")
    
    # Ensure uploads and database directories exist
    os.makedirs("uploads", exist_ok=True)
    
    # Start server
    try:
        subprocess.run([
            sys.executable, 
            "-m", "app.main"
        ])
    except KeyboardInterrupt:
        print("\nServer has been stopped")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Ensure script is run from project root directory
    if not (os.path.exists("backend") and os.path.exists("backend/app")):
        print("Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Check environment
    check_requirements()
    
    # Start server
    start_server()