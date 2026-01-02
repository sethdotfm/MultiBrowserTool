import yaml
import os

def load_config():
    """Loads types.yaml and config.yaml and merges them."""
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    types_path = os.path.join(base_dir, 'types.yaml')
    config_path = os.path.join(base_dir, 'config.yaml')

    try:
        with open(types_path, 'r') as f:
            types_def = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: {types_path} not found.")
        return None

    try:
        with open(config_path, 'r') as f:
            config_def = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: {config_path} not found.")
        return None
        
    # Helper to resolve system configuration
    resolved_systems = {}
    
    for group_key, group_data in config_def.get('systems', {}).items():
        resolved_systems[group_key] = {
            'name': group_data.get('name'),
            'systems': {}
        }
        for sys_key, sys_data in group_data.get('systems', {}).items():
            sys_type = sys_data.get('type')
            if sys_type not in types_def:
                print(f"Warning: Unknown system type '{sys_type}' for '{sys_key}'")
                continue
                
            type_info = types_def[sys_type]
            
            # Merge defaults from type_info with instance specific sys_data
            # Instance data overrides type data
            merged_sys = type_info.copy()
            merged_sys.update(sys_data)
            
            # Ensure actions are present
            if 'actions' not in merged_sys:
                merged_sys['actions'] = {}
                
            resolved_systems[group_key]['systems'][sys_key] = merged_sys

    config_def['resolved_systems'] = resolved_systems
    config_def['types'] = types_def
    
    return config_def
