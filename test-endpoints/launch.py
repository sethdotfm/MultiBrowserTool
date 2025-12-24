import os
import sys
import subprocess
import time
import glob
import yaml
import platform
import webbrowser
from typing import Dict, List, Optional

# Constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class EndpointManager:
    def __init__(self):
        self.endpoints: Dict[str, Dict] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        
    def discover_endpoints(self):
        """Finds all subdirectories with test-page.app.py and config.yaml"""
        self.endpoints = {}
        pattern = os.path.join(BASE_DIR, "*", "test-page.app.py")
        app_files = glob.glob(pattern)
        
        for app_file in app_files:
            app_dir = os.path.dirname(app_file)
            dir_name = os.path.basename(app_dir)
            config_file = os.path.join(app_dir, "config.yaml")
            
            if not os.path.exists(config_file):
                print(f"Warning: No config.yaml found for {dir_name}, skipping.")
                continue
                
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                    
                port = config.get('server', {}).get('port', 5000)
                self.endpoints[dir_name] = {
                    'name': dir_name,
                    'dir': app_dir,
                    'app_file': app_file,
                    'port': port,
                    'config': config
                }
            except Exception as e:
                print(f"Error loading config for {dir_name}: {e}")

    def start_endpoint(self, name: str):
        if name not in self.endpoints:
            print(f"Endpoint '{name}' not found.")
            return
        
        if name in self.processes and self.processes[name].poll() is None:
            print(f"Endpoint '{name}' is already running.")
            return

        endpoint = self.endpoints[name]
        print(f"Starting {name} on port {endpoint['port']}...")
        
        # Windows specific: Open in new console window
        kwargs = {}
        if platform.system() == 'Windows':
            kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE
        
        try:
            # Launch the flask app
            proc = subprocess.Popen(
                [sys.executable, "test-page.app.py"],
                cwd=endpoint['dir'],
                **kwargs
            )
            self.processes[name] = proc
            print(f"Started {name} (PID: {proc.pid})")
        except Exception as e:
            print(f"Failed to start {name}: {e}")

    def stop_endpoint(self, name: str):
        if name in self.processes:
            proc = self.processes[name]
            if proc.poll() is None:
                print(f"Stopping {name} (PID: {proc.pid})...")
                
                try:
                    if platform.system() == 'Windows':
                        # Force kill the process tree to handle new console windows and Flask reloader
                        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], 
                                     stdout=subprocess.DEVNULL, 
                                     stderr=subprocess.DEVNULL)
                    else:
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                    
                    print(f"Stopped {name}")
                except Exception as e:
                    print(f"Error stopping {name}: {e}")
            else:
                 print(f"{name} was already stopped.")
            del self.processes[name]
        else:
            print(f"Endpoint '{name}' is not running.")

    def restart_endpoint(self, name: str):
        self.stop_endpoint(name)
        time.sleep(1)
        self.start_endpoint(name)

    def launch_kiosk(self, name: str):
        if name not in self.endpoints:
             print(f"Endpoint '{name}' not found.")
             return
        
        endpoint = self.endpoints[name]
        url = f"http://localhost:{endpoint['port']}"
        print(f"Opening {name} in Kiosk mode ({url})...")
        
        # Try to find Chrome
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
             # Fallback for generic 'chrome' in PATH
            "chrome"
        ]
        
        cmd = None
        for path in chrome_paths:
            if path == "chrome" or os.path.exists(path):
                cmd = path
                break
        
        if cmd:
            try:
                subprocess.Popen([cmd, "--kiosk", "--new-window", url])
            except FileNotFoundError:
                print("Could not launch chrome. Please ensure it is installed or in PATH.")
                webbrowser.open(url) # Fallback to default browser
        else:
            print("Chrome executable not found. Opening default browser.")
            webbrowser.open(url)


    def status(self):
        print("\n--- Endpoint Status ---")
        if not self.endpoints:
            print("No endpoints discovered.")
            return

        for name, data in self.endpoints.items():
            status = "STOPPED"
            if name in self.processes:
                if self.processes[name].poll() is None:
                    status = "RUNNING"
                else:
                    status = "EXITED"
            print(f"{name: <15} Port: {data['port']: <6} Status: {status}")
        print("-----------------------")

def print_help():
    print("""
Commands:
  status, list        - Show status of all endpoints
  start [all|name]    - Start specific endpoint or all
  stop [all|name]     - Stop specific endpoint or all
  restart [all|name]  - Restart specific endpoint or all
  kiosk [all|name]    - Open endpoint(s) in Kiosk mode
  reload              - Rediscover endpoints from disk
  help                - Show this help message
  quit, exit          - Stop all and exit
""")

def main():
    manager = EndpointManager()
    manager.discover_endpoints()
    print(f"Found {len(manager.endpoints)} endpoints.")
    print_help()
    
    while True:
        try:
            user_input = input("cmd> ").strip().lower()
        except KeyboardInterrupt:
            break
            
        if not user_input:
            continue
            
        parts = user_input.split()
        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else None
        
        if cmd in ["quit", "exit"]:
            print("Stopping all processes...")
            for name in list(manager.processes.keys()):
                manager.stop_endpoint(name)
            break
            
        elif cmd in ["status", "list"]:
            manager.status()
            
        elif cmd == "help":
            print_help()
            
        elif cmd == "reload":
            manager.discover_endpoints()
            print("Endpoints reloaded.")
            
        elif cmd == "start":
            if arg == "all" or arg is None:
                for name in manager.endpoints:
                    manager.start_endpoint(name)
            else:
                manager.start_endpoint(arg)
                
        elif cmd == "stop":
            if arg == "all" or arg is None:
                for name in list(manager.processes.keys()):
                    manager.stop_endpoint(name)
            else:
                manager.stop_endpoint(arg)
                
        elif cmd == "restart":
            if arg == "all" or arg is None:
                for name in manager.endpoints:
                    if name in manager.processes: # Only restart running ones? Or start all?
                         # "Restart" usually implies restarting active ones, or resetting everything. 
                         # Let's assume restart active ones if no arg, or if "all" specified, restart all (start if stopped).
                         manager.restart_endpoint(name)
                    else:
                        manager.start_endpoint(name)
            else:
                manager.restart_endpoint(arg)

        elif cmd == "kiosk":
            if arg == "all" or arg is None:
                for name in manager.endpoints:
                    manager.launch_kiosk(name)
            else:
                manager.launch_kiosk(arg)
        else:
            print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()
