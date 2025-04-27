#!/usr/bin/env python3
"""
Simple script to test file structure in the container
"""
import os
import sys
import glob

print("\n=== PYTHON TEST FILE ===")
print(f"Running from: {__file__}")
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

print("\n=== PYTHON PATH ===")
for i, path in enumerate(sys.path):
    print(f"  {i}: {path}")

print("\n=== ENVIRONMENT VARIABLES ===")
for key, value in sorted(os.environ.items()):
    if key in ['PYTHONPATH', 'PATH', 'HOME', 'PORT', 'PWD']:
        print(f"  {key}={value}")

print("\n=== DIRECTORY LISTING ===")
try:
    for directory in ['/', '/app', '/tmp', '/home']:
        if os.path.exists(directory):
            print(f"\nListing {directory}:")
            files = os.listdir(directory)
            for f in files:
                path = os.path.join(directory, f)
                if os.path.isdir(path):
                    print(f"  {f}/")
                else:
                    size = os.path.getsize(path)
                    print(f"  {f} ({size} bytes)")
except Exception as e:
    print(f"Error listing directories: {e}")

print("\n=== SEARCHING FOR PYTHON FILES ===")
try:
    for directory in ['/', '/app', '/tmp', '/home']:
        if os.path.exists(directory):
            print(f"\nSearching {directory} for .py files:")
            py_files = glob.glob(f"{directory}/**/*.py", recursive=True)
            for f in py_files[:15]:  # Limit to first 15 to avoid flooding output
                print(f"  {f}")
            if len(py_files) > 15:
                print(f"  ... and {len(py_files) - 15} more")
except Exception as e:
    print(f"Error searching for .py files: {e}")

print("\n=== TRYING TO IMPORT MAIN ===")
try:
    import main
    print("Successfully imported 'main'")
    if hasattr(main, 'app'):
        print("'main' module has 'app' attribute")
    else:
        print("'main' module does not have 'app' attribute")
except ImportError as e:
    print(f"Failed to import 'main': {e}")
    
    print("\nAttempting to locate main.py:")
    for directory in ['/', '/app', '/tmp', '/home']:
        main_path = os.path.join(directory, 'main.py')
        if os.path.exists(main_path):
            print(f"  Found at {main_path}")
            with open(main_path, 'r') as f:
                print(f"  First 5 lines of {main_path}:")
                for i, line in enumerate(f.readlines()[:5]):
                    print(f"    {i+1}: {line.strip()}")
            
    # Try to diagnose why import failed
    print("\nDiagnosing import failure:")
    for path in sys.path:
        if os.path.isdir(path):
            main_in_path = os.path.join(path, 'main.py')
            if os.path.exists(main_in_path):
                print(f"  main.py exists in path '{path}' but import still failed")
    
print("\n=== DONE ===")
if __name__ == "__main__":
    print("Script ran successfully.") 