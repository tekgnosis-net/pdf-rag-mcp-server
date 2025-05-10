#!/usr/bin/env python3
"""
Script to build the PDF Knowledge Base System.

This script builds the frontend, copies the build output to the backend's static directory,
enabling the FastAPI backend server to serve the frontend files.
"""

import os
import shutil
import subprocess
import sys

def build_frontend():
    """Build the frontend application"""
    print("Building frontend application...")
    os.chdir("frontend")
    
    # Install dependencies
    print("Installing frontend dependencies...")
    subprocess.run(['npm', 'install'], check=True)
    
    # Build frontend
    print("Building frontend...")
    subprocess.run(['npm', 'run', 'build'], check=True)
    
    os.chdir("..")
    
    # Copy build output to backend static directory
    print("Copying frontend build output to backend static directory...")
    if os.path.exists("frontend/dist"):
        # Clean static directory
        if os.path.exists("backend/app/static"):
            for item in os.listdir("backend/app/static"):
                item_path = os.path.join("backend/app/static", item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
        else:
            os.makedirs("backend/app/static", exist_ok=True)
            
        # Copy build output
        for item in os.listdir("frontend/dist"):
            src_path = os.path.join("frontend/dist", item)
            dst_path = os.path.join("backend/app/static", item)
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)
        print("Frontend build output has been copied to backend static directory")
    else:
        print("Error: Frontend build directory does not exist!")
        sys.exit(1)

def main():
    """Main function"""
    # Ensure running from project root directory
    if not (os.path.isdir("frontend") and os.path.isdir("backend")):
        print("Error: Please run this script from the project root directory!")
        sys.exit(1)
        
    # Build frontend
    build_frontend()
    


if __name__ == "__main__":
    main() 
