import os
import glob
import sys
import importlib
import subprocess

# Clear bytecode cache files
def clean_cache():
    # Find and remove all __pycache__ directories and .pyc files
    for pycache_dir in glob.glob('**/__pycache__', recursive=True):
        print(f"Removing {pycache_dir}")
        for pyc_file in glob.glob(f'{pycache_dir}/*.pyc'):
            print(f"Removing {pyc_file}")
            os.remove(pyc_file)
    
    print("Cache cleaned!")

# Force reload modules
def reload_modules():
    modules_to_reload = [
        'routes.notifications',
        'routes',
        'app'
    ]
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            print(f"Reloading {module_name}")
            importlib.reload(sys.modules[module_name])
    
    print("Modules reloaded!")

# Run the app
def run_app():
    print("Starting app.py...")
    subprocess.run(["python", "app.py"])

if __name__ == "__main__":
    clean_cache()
    reload_modules()
    run_app() 