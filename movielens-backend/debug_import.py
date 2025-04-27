#!/usr/bin/env python3
"""
Debug script to check module import paths and Python environment
"""
import sys
import os
import importlib.util

def check_module_exists(module_name, folder):
    """Check if a module exists and can be imported"""
    try:
        file_path = os.path.join(folder, f"{module_name}.py")
        if os.path.exists(file_path):
            print(f"✅ {module_name}.py file exists at: {file_path}")
        else:
            print(f"❌ {module_name}.py file does not exist at: {file_path}")
            return False
        
        # Try to import it
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None:
            print(f"❌ Could not create spec for {module_name} at {file_path}")
            return False
            
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        print(f"✅ Successfully imported {module_name} from {file_path}")
        return True
    except Exception as e:
        print(f"❌ Error importing {module_name}: {str(e)}")
        return False

def main():
    """Main debug function"""
    print("\n=== PYTHON ENVIRONMENT DEBUG ===")
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
    print(f"sys.path: {sys.path}")
    
    print("\n=== CHECKING FOR main MODULE ===")
    # Check in current directory
    check_module_exists("main", os.getcwd())
    
    # Check in /app directory
    if os.path.exists("/app"):
        check_module_exists("main", "/app")
    
    # Check in all sys.path directories
    for path in sys.path:
        if path and os.path.exists(path) and path != os.getcwd() and path != "/app":
            check_module_exists("main", path)
    
    print("\n=== FILE SYSTEM EXPLORATION ===")
    print("Files in current directory:")
    for item in os.listdir(os.getcwd()):
        print(f" - {item}")
    
    if os.path.exists("/app"):
        print("\nFiles in /app directory:")
        for item in os.listdir("/app"):
            print(f" - {item}")

if __name__ == "__main__":
    main() 