# MultiBrowserTool Overview

I work as a broadcast engineer on virtual production sets and large scale corporate events. We use a variety of different systems with different methods of executing commands like "Record". I have to switch between multiple browser windows to execute these commands. This is time consuming and error prone. So, we are creating a tool to execute these commands from a single interface.

To begin, we will be supporting only two systems: Sony VENICE 2, and AJA KiPro. However, this should be extensible to support other systems in the future via a simple config.yaml file.
To do this, we will use types.yaml to define the parameters of systems and the commands they support. Then, we will use config.yaml to define the user interface and the mapping of interface elements to system commands.
The interface will be a simple web inteface hosted by Flask. The design is a large header with system information, time, and socket connection status. Below is a spreadsheet type view, where the header row is "ALL", subsequent rows are groups of systems as defined in config.yaml, and their children are individual endpoints as defined in config.yaml. Columns are Name, Status, and any commands as defined in config.yaml. There is an expandable section off the right side to view more columns for debugging, including IP address, port, and the last executed command.

For types.yaml, we will begin with a single execution method: JS Injection. We will use playwright to inject JS into the DOM.

A first draft of the .yaml files are as follows:

```yaml
# types.yaml

venice2: # System definition
    name: "Sony VENICE 2" # Friendly name, fallback to system def if blank
    type: "camera" # Type (may be implemented for grouping?)
    url: "http://192.168.1.100" # Device default URL
    port: 80 # Device default port
    path: "/rmt.html" # Device default path
    browser_auth: # Browser device authentication
        username: "admin" # Device default username
        password: "password" # Device default password
    actions:
        toggle_record: # Action definition
            name: "Toggle Record" # Friendly name, fallback to action def if blank
            js_injection: "document.getElementById('record').click()" # JS to inject

kipro:
    name: "AJA KiPro" # Friendly name, fallback to system def if blank
    type: "recorder" # Type (may be implemented for grouping?)
    url: "http://192.168.1.200" # Device default URL
    port: 8080 # Device default port
    path: "/" # Device default path
    actions:
        start_record: # Action definition
            name: "Start Record" # Friendly name, fallback to action def if blank
            js_injection: "document.getElementById('start_record').click()" # JS to inject
        stop_record: # Action definition
            name: "Stop Record" # Friendly name, fallback to action def if blank
            js_injection: "document.getElementById('stop_record').click()" # JS to inject

```

```yaml
# config.yaml

port: 80 # Flask server port
page_title: "MultiBrowserTool" # Flask server page title

systems: # Columns
    group:
        name: "Cameras" # Friendly name, required
        systems:
            venice2: # Type name, required
                name: "Camera 1" # Friendly name, fallback to type def if blank
                url: "http://192.168.1.101" # Device URL
                browser_auth: # Browser device authentication
                    username: "admin" # Device username
                    password: "super_secret_password" # Device password
            venice2: # Type name, required
                name: "Camera 2" # Friendly name, fallback to type def if blank
                url: "http://192.168.1.102" # Device URL
                browser_auth: # Browser device authentication
                    username: "admin" # Device username
                    password: "super_secret_password" # Device password
    group:
        name: "Recorders" # Friendly name, required
        systems:
            kipro: # Type name, required
                name: "KiPro 1" # Friendly name, fallback to type def if blank
                url: "http://192.168.1.201" # Device URL
                browser_auth: # Browser device authentication
                    username: "admin" # Device username
                    password: "super_secret_password" # Device password

actions: # Rows 
    start_record: # Action name, required
        name: "Start Record" # Friendly name, fallback to action def if blank
        systems: venice2
            execute: toggle_record
        systems: kipro
            execute: start_record
    stop_record: # Action name, required
        name: "Stop Record" # Friendly name, fallback to action def if blank
        systems: venice2
            execute: toggle_record
        systems: kipro
            execute: stop_record

```