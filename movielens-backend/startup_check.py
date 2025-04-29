#!/usr/bin/env python3
"""
Startup check script to diagnose Python import issues in Cloud Run.
This script prints diagnostic information about the environment.
"""
import os
import sys
import json
import importlib.util

def check_file_exists(filepath):
    """Check if a file exists and print its size."""
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        return f"✅ Exists ({size} bytes)"
    else:
        return "❌ Not found"

def get_module_path(module_name):
    """Try to find the path of a module."""
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is not None:
            return f"✅ Found at {spec.origin}"
        else:
            return "❌ Not found in Python path"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def main():
    """Print diagnostic information."""
    diagnostics = {
        "python_version": sys.version,
        "python_path": sys.path,
        "current_directory": os.getcwd(),
        "directory_contents": os.listdir(),
        "environment_variables": {k: v for k, v in os.environ.items() if k in ["PYTHONPATH", "PATH", "PORT"]},
        "file_checks": {
            "main.py": check_file_exists("main.py"),
            "run.py": check_file_exists("run.py"),
            "app directory": check_file_exists("app")
        },
        "module_checks": {
            "main": get_module_path("main"),
            "app": get_module_path("app"),
            "app.api.api": get_module_path("app.api.api")
        }
    }
    
    print("\n===== STARTUP DIAGNOSTICS =====\n")
    print(json.dumps(diagnostics, indent=2))
    print("\n===============================\n")

if __name__ == "__main__":
    main() 