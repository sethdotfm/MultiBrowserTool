import os
import time
import yaml
from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Load configuration
def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

config = load_config()
port = config.get('server', {}).get('port', 5000)
elements = config.get('elements', [])
identifier = config.get('identifier', {})

@app.route('/')
def index():
    # Reload config to get latest changes
    config = load_config()
    elements = config.get('elements', [])
    identifier = config.get('identifier', {})
    return render_template('index.html', elements=elements, identifier=identifier)

@app.route('/log_action', methods=['POST'])
def log_action():
    data = request.json
    # High precision server time
    server_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    # We echo back the data with the server timestamp
    response = {
        'server_time': server_time,
        'id': data.get('id'),
        'action': data.get('action'),
        'value': data.get('value')
    }
    
    # Also print to server console for verification
    print(f"[{server_time}] ID={data.get('id')} ACTION={data.get('action')} VAL={data.get('value')}")
    
    return jsonify(response)

if __name__ == '__main__':
    print(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
