from playwright.sync_api import sync_playwright
import threading
import queue
import time

class BrowserManager:
    def __init__(self, config, status_callback=None):
        self.config = config
        self.status_callback = status_callback
        self.command_queue = queue.Queue()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.started = False
        
    def start(self):
        """Starts the browser worker thread."""
        if not self.started:
            self.thread.start()
            self.started = True

    def _update_status(self, sys_id, status, statuses_dict):
        """Helper to update status dict and notify callback."""
        # statuses_dict is reference to the dict inside the thread
        if statuses_dict.get(sys_id) != status:
            statuses_dict[sys_id] = status
            print(f"Status Change: {sys_id} -> {status}")
            if self.status_callback:
                self.status_callback(sys_id, status)
            
    def _run_loop(self):
        """The main loop running in a separate thread."""
        headless = self.config.get('headless', False)
        print(f"Starting Playwright Thread (Headless: {headless})...")
        
        # Local state for this thread
        current_statuses = {} 

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, args=['--disable-infobars'])
            
            # Map system_id -> page
            pages = {}
            contexts = {}

            def init_system(sys_id, sys_data):
                nonlocal current_statuses
                
                try:
                    if sys_id in pages:
                         # Close existing
                         try: pages[sys_id].close()
                         except: pass
                         del pages[sys_id]
                    if sys_id in contexts:
                         try: contexts[sys_id].close()
                         except: pass
                         del contexts[sys_id]

                    self._update_status(sys_id, 'CONNECTING', current_statuses)
                    print(f"Initializing {sys_data['name']} ({sys_id})...")
                    
                    context = browser.new_context(
                        viewport={'width': 1280, 'height': 720},
                        http_credentials=sys_data.get('browser_auth')
                    )
                    page = context.new_page()
                    
                    # Attach listeners
                    page.on("close", lambda: self._update_status(sys_id, 'OFFLINE', current_statuses))
                    page.on("crash", lambda: self._update_status(sys_id, 'ERROR', current_statuses))
                    
                    url = sys_data.get('url')
                    path = sys_data.get('path', '')
                    full_url = f"{url}{path}"
                    
                    try:
                        page.goto(full_url, timeout=5000)
                        print(f"Loaded {full_url}")
                        self._update_status(sys_id, 'ONLINE', current_statuses)
                    except Exception as e:
                        print(f"Failed to load {full_url}: {e}")
                        self._update_status(sys_id, 'ERROR', current_statuses)
                    
                    pages[sys_id] = page
                    contexts[sys_id] = context
                    return True
                except Exception as e:
                    print(f"Error initializing system {sys_id}: {e}")
                    self._update_status(sys_id, 'ERROR', current_statuses)
                    return False
            
            # Initial Startup
            systems = self.config.get('resolved_systems', {})
            for group in systems.values():
                for sys_id, sys_data in group['systems'].items():
                    # Set initial status to STOPPED if not in loop yet
                    current_statuses[sys_id] = 'STOPPED' 
                    init_system(sys_id, sys_data)

            # Message Loop
            last_poll_time = 0
            while True:
                # 1. Process all pending commands in queue first
                try:
                    while True: # Drain queue
                        task = self.command_queue.get_nowait()
                        
                        if task is None: # Sentinel to exit
                            browser.close()
                            print("Browser thread closed.")
                            return

                        cmd_type, data, result_queue = task

                        try:
                            if cmd_type == 'execute':
                                sys_id, js_code = data
                                if sys_id in pages and not pages[sys_id].is_closed():
                                    print(f"Executing on {sys_id}: {js_code}")
                                    try:
                                        pages[sys_id].evaluate(js_code)
                                        result_queue.put({'success': True, 'message': 'Executed'})
                                    except Exception as e:
                                        result_queue.put({'success': False, 'message': str(e)})
                                        self._update_status(sys_id, 'ERROR', current_statuses)
                                else:
                                    result_queue.put({'success': False, 'message': 'System not found or offline'})
                            
                            elif cmd_type == 'restart':
                                target_id = data
                                restarted = []
                                if target_id == 'all':
                                    for group in systems.values():
                                        for sys_id, sys_data in group['systems'].items():
                                            if init_system(sys_id, sys_data):
                                                restarted.append(sys_id)
                                else:
                                     found = False
                                     for group in systems.values():
                                         if target_id in group['systems']:
                                             if init_system(target_id, group['systems'][target_id]):
                                                 restarted.append(target_id)
                                             found = True
                                             break
                                     if not found:
                                         result_queue.put({'success': False, 'message': 'System not found'})
                                         continue
                                result_queue.put({'success': True, 'restarted': restarted})

                            elif cmd_type == 'status':
                                result_queue.put(current_statuses.copy())

                        except Exception as e:
                            print(f"Error processing task {cmd_type}: {e}")
                            result_queue.put({'success': False, 'message': str(e)})

                except queue.Empty:
                    pass

                # 2. Pump Playwright Events (Idle)
                # Sync Playwright needs API calls to process events.
                pumped = False
                if pages:
                    # Use the first available page to pump the event loop
                    try:
                        # Find a valid page
                        for p_obj in pages.values():
                            if not p_obj.is_closed():
                                p_obj.wait_for_timeout(100) # Wait 100ms, allows events to fire
                                pumped = True
                                break
                    except:
                        pass
                
                if not pumped:
                    time.sleep(0.1)

                # 3. Throttled Polling Check (every 2 seconds)
                if time.time() - last_poll_time > 2.0:
                    last_poll_time = time.time()
                    for group in systems.values():
                        for sys_id in group['systems']:
                            if sys_id in pages:
                                try:
                                    if pages[sys_id].is_closed():
                                        self._update_status(sys_id, 'CLOSED', current_statuses)
                                except Exception as e:
                                    if current_statuses.get(sys_id) not in ['ERROR', 'CLOSED']:
                                        print(f"Polling error for {sys_id}: {e}")
                                        self._update_status(sys_id, 'ERROR', current_statuses)
                            else:
                                if current_statuses.get(sys_id) != 'STOPPED':
                                    self._update_status(sys_id, 'STOPPED', current_statuses)


    def execute_command(self, sys_id, action_name):
        """Public API called from Flask thread."""
        
        # 1. Resolve JS code (safe to do here)
        system_config = self._get_system_config(sys_id)
        if not system_config:
             return {'success': False, 'message': 'System config not found'}

        actions = system_config.get('actions', {})
        if action_name not in actions:
             return {'success': False, 'message': f'Action {action_name} not supported by this system'}
        
        js_code = actions[action_name].get('js_injection')
        if not js_code:
            return {'success': False, 'message': 'No JS code defined'}

        # 2. Send to worker thread
        result_queue = queue.Queue()
        self.command_queue.put(('execute', (sys_id, js_code), result_queue))
        
        try:
            return result_queue.get(timeout=10)
        except queue.Empty:
            return {'success': False, 'message': 'Timeout waiting for browser thread'}

    def restart_system(self, sys_id):
        """Restarts a specific system or 'all'."""
        result_queue = queue.Queue()
        self.command_queue.put(('restart', sys_id, result_queue))
        try:
            return result_queue.get(timeout=30) # Longer timeout for restart
        except queue.Empty:
            return {'success': False, 'message': 'Timeout waiting for browser thread'}

    def get_status(self):
        """Gets status of all systems."""
        result_queue = queue.Queue()
        self.command_queue.put(('status', None, result_queue))
        try:
            return result_queue.get(timeout=5)
        except queue.Empty:
            return {}

    def _get_system_config(self, target_sys_id):
        systems = self.config.get('resolved_systems', {})
        for group in systems.values():
            for sys_id, data in group['systems'].items():
                if sys_id == target_sys_id:
                    # Return a copy to be safe, though config is treated as read-only
                    return data
        return None

    def close(self):
        self.command_queue.put(None)
        if self.started:
            self.thread.join()
