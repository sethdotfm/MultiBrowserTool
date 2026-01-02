import os
import sys
from config_loader import load_config
from browser import BrowserManager
import time

def verify():
    print("Verifying Config Loader...")
    config = load_config()
    if not config:
        print("FAIL: Config not loaded")
        sys.exit(1)
    
    print(f"Config loaded. Page Title: {config.get('page_title')}")
    systems = config.get('resolved_systems', {})
    print(f"Systems found: {len(systems)}")
    
    # Check for emulators
    found_venice = False
    for group in systems.values():
        for sys_id, sys_data in group['systems'].items():
            print(f" - {sys_id}: {sys_data['url']}")
            if sys_data['type'] == 'venice2':
                found_venice = True
    
    if not found_venice:
        print("WARN: Venice2 system not found in config")

    print("\nVerifying Browser Manager...")
    # Force headless for verification unless user really wants to see it
    # config['headless'] = True 
    bm = BrowserManager(config)
    
    try:
        bm.start()
        print("Browser started.")
        
        # Wait a bit for contexts to load
        time.sleep(2)
        
        print(f"Active contexts: {len(bm.contexts)}")
        if len(bm.contexts) == 0:
             print("FAIL: No contexts created.")
             # sys.exit(1) # Don't exit yet, might be due to connection ref used
        
        # Test command execution on a fake system or real one if available
        # We can't easily test execution without a running server on those ports
        # But we can try to execute and expect a failure message or success if emulators are running.
        # Since emulators might NOT be running, we expect connection errors or timeouts, but the code shouldn't crash.
        
        print("Test execution on 'camera1'...")
        result = bm.execute_command('camera1', 'toggle_record')
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"FAIL: Browser verification failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Closing browser...")
        bm.close()
        print("Done.")

if __name__ == "__main__":
    verify()
