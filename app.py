#                                                                      
#    _____     _ _   _ _____                           _____         _ 
#   |     |_ _| | |_|_| __  |___ ___ _ _ _ ___ ___ ___|_   _|___ ___| |
#   | | | | | | |  _| | __ -|  _| . | | | |_ -| -_|  _| | | | . | . | |
#   |_|_|_|___|_|_| |_|_____|_| |___|_____|___|___|_|   |_| |___|___|_|
#                                                                   
# 
#   A simple Flask/Playwright app to click buttons on several webpages simultaneously.
#   Written, with vibes, by Seth, in Seattle.
#   
#   https://github.com/sethdotfm/MultiBrowserTool
#   20260102 v0.1

import os
import threading
import cmd
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from config_loader import load_config
from browser import BrowserManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='threading')

# Load Configuration
config = load_config()
if not config:
    print("Failed to load configuration. Exiting.")
    exit(1)

# Initialize Browser Manager
# We need to broadcast status updates to UI
def on_browser_status_change(sys_id, status):
    print(f"[App] Status update: {sys_id} -> {status}")
    socketio.emit('status_update', {'system_id': sys_id, 'status': status})

browser_manager = BrowserManager(config, status_callback=on_browser_status_change)

# Global start removed to prevent double-start with reloader checks in main

@app.route('/')
def index():
    return render_template('index.html', config=config)

@socketio.on('request_status')
def handle_request_status():
    """UI requests full status snapshot on connect"""
    status = browser_manager.get_status()
    socketio.emit('full_status_update', status)

@socketio.on('execute_command')
def handle_execution(data):
    """
    Received data: { 'system_id': 'camera1', 'action_id': 'record_toggle' }
    """
    sys_id = data.get('system_id')
    abstract_action = data.get('action_id')
    
    print(f"Request: {abstract_action} on {sys_id}")
    
    # Resolve the abstract action from config.yaml to the specific system action
    # 1. Find the system type
    sys_config = browser_manager._get_system_config(sys_id)
    if not sys_config:
        emit('command_result', {'system_id': sys_id, 'status': 'error', 'message': 'System not found'})
        return

    sys_type = sys_config.get('type')
    
    # 2. Look up the mapping in config['actions']
    action_config = config['actions'].get(abstract_action)
    if not action_config:
         emit('command_result', {'system_id': sys_id, 'status': 'error', 'message': 'Unknown action'})
         return
         
    mappings = action_config.get('mappings', {})
    target_action = mappings.get(sys_type)
    
    if not target_action:
        # Not mapped for this system type, maybe ignore or error?
        # If the button exists on UI, it should probably be mapped.
        emit('command_result', {'system_id': sys_id, 'status': 'error', 'message': 'Action not supported'})
        return

    # 3. Execute
    result = browser_manager.execute_command(sys_id, target_action)
    
    status = 'success' if result['success'] else 'error'
    emit('command_result', {
        'system_id': sys_id, 
        'action_id': abstract_action,
        'status': status, 
        'message': result['message']
    })

@app.route('/api/status')
def get_status():
    return jsonify({'status': 'running'})

@app.route('/api/admin/status', methods=['GET'])
def admin_status():
    status = browser_manager.get_status()
    return jsonify(status)

@app.route('/api/admin/restart', methods=['POST'])
def admin_restart():
    data = request.json or {}
    target = data.get('system_id', 'all')
    result = browser_manager.restart_system(target)
    return jsonify(result)

@app.route('/api/admin/shutdown', methods=['POST'])
def admin_shutdown():
    # Helper to stop the server
    browser_manager.close()
    os._exit(0) # Force exit
    return 'Shutting down...'

class AppShell(cmd.Cmd):
    intro = 'Welcome to the MultiBrowserTool CLI. Type help or ? to list commands.\n'
    prompt = '(mbt) '

    def do_status(self, arg):
        """Show system status"""
        status = browser_manager.get_status()
        print(f"\n{'SYSTEM':<20} {'STATUS':<10}")
        print("-" * 30)
        for sys_id, state in status.items():
            print(f"{sys_id:<20} {state:<10}")
        print("") # Newline

    def do_restart(self, arg):
        """Restart sessions. Usage: restart [all|system_id]"""
        target = arg if arg else 'all'
        print(f"Restarting {target}...")
        result = browser_manager.restart_system(target)
        
        if result.get('success'):
            print("Success.")
            if 'restarted' in result:
                print(f"Restarted: {', '.join(result['restarted'])}")
        else:
             print(f"Failed: {result.get('message')}")

    def do_shutdown(self, arg):
        """Shutdown the server"""
        print("Shutting down...")
        browser_manager.close()
        os._exit(0)

    def do_quit(self, arg):
        """Exit the debug shell (server continues)"""
        print("Exiting shell...")
        return True

def run_shell():
    try:
        AppShell().cmdloop()
    except Exception as e:
        print(f"Shell error: {e}")

if __name__ == '__main__':
    port = config.get('port', 5000)
    print(f"Starting server on port {port}")
    
    # Check if we are in the reloader child process (or if reloader is disabled)
    # WERKZEUG_RUN_MAIN is 'true' in the child process
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        browser_manager.start()
        
        # Start CLI Thread
        t = threading.Thread(target=run_shell, daemon=True)
        t.start()
        
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
