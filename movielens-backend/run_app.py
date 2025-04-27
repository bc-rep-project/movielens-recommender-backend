#!/usr/bin/env python3
"""
Direct Python entry point for the application.
This script handles importing the FastAPI app and starting uvicorn directly.
"""
import os
import sys
import traceback
import importlib.util
import subprocess
import threading
import time

def log(message):
    """Print a log message with timestamp"""
    print(f"[STARTUP] {message}", flush=True)

def run_command(cmd):
    """Run a shell command and return output"""
    try:
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
        return output.strip()
    except subprocess.CalledProcessError as e:
        return f"Error ({e.returncode}): {e.output.strip()}"

def log_environment():
    """Log environment information for debugging"""
    log("=== ENVIRONMENT INFO ===")
    log(f"Current directory: {os.getcwd()}")
    log(f"Python path: {sys.path}")
    log(f"Python version: {sys.version}")
    log(f"Python executable: {sys.executable}")
    
    # Log environment variables
    log("Environment variables:")
    for key, value in sorted(os.environ.items()):
        if key in ('PYTHONPATH', 'PATH', 'PWD', 'HOME'):
            log(f"  {key}={value}")
    
    # Run some system commands
    log("Process info:")
    log(f"  PID: {os.getpid()}")
    log(f"  Process list: {run_command('ps aux | grep python')}")
    
    log("Directory contents:")
    for root, dirs, files in os.walk("/app", topdown=True, followlinks=False):
        level = root.replace("/app", "").count(os.sep)
        indent = "  " * level
        log(f"{indent}{os.path.basename(root)}/")
        for f in files:
            log(f"{indent}  {f}")

def start_healthcheck_server():
    """Start a simple health check server on a separate thread"""
    try:
        log("Starting health check server on port 8081")
        subprocess.Popen(["python3", "/app/healthcheck.py"])
    except Exception as e:
        log(f"Error starting healthcheck server: {e}")

def load_module_from_file(file_path, module_name="main"):
    """Load a module directly from a file path"""
    log(f"Loading module '{module_name}' from {file_path}")
    if not os.path.exists(file_path):
        log(f"ERROR: File {file_path} does not exist!")
        return None
    
    try:
        # Print file content for debugging
        with open(file_path, 'r') as f:
            log(f"File content of {file_path}:")
            for i, line in enumerate(f.readlines()[:20]):  # Display first 20 lines
                log(f"  {i+1}: {line.rstrip()}")
            log("  ...")
        
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None:
            log(f"ERROR: Failed to create spec for {module_name} from {file_path}")
            return None
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        log(f"Successfully loaded module '{module_name}'")
        return module
    except Exception as e:
        log(f"ERROR loading module: {e}")
        log(traceback.format_exc())
        return None

def run_server():
    """Main function to run the server"""
    try:
        log("Starting application...")
        
        # Run startup test script to verify Python is working
        log("Running startup test...")
        exec(open("/app/startup_test.py").read())
        
        # Log environment info
        log_environment()
        
        # Start health check server
        threading.Thread(target=start_healthcheck_server, daemon=True).start()
        
        # Ensure /app is in Python path
        app_dir = "/app"
        if app_dir not in sys.path:
            log(f"Adding {app_dir} to Python path")
            sys.path.insert(0, app_dir)
        
        # Try multiple import strategies
        app = None
        
        # Strategy 1: Regular import
        log("\n=== IMPORT STRATEGY 1: Regular Import ===")
        try:
            log("Attempting regular import...")
            import main
            log("Regular import succeeded")
            app = main.app
        except ImportError as e:
            log(f"Regular import failed: {e}")
        
        # Strategy 2: Direct file import
        if app is None:
            log("\n=== IMPORT STRATEGY 2: Direct File Import ===")
            log("Trying direct file import...")
            main_path = os.path.join(app_dir, "main.py")
            main_module = load_module_from_file(main_path)
            if main_module is not None:
                app = getattr(main_module, 'app', None)
                if app is None:
                    log("ERROR: 'app' not found in main module")
        
        # If all strategies failed, exit
        if app is None:
            log("All import strategies failed. Cannot start the server.")
            sys.exit(1)
        
        log("Successfully got app object. Starting uvicorn server...")
        os.chdir(app_dir)  # Ensure we're in the right directory
        
        # Start uvicorn directly
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
    
    except Exception as e:
        log(f"CRITICAL ERROR: {e}")
        log(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    run_server() 