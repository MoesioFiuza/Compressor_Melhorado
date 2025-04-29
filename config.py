import os
import json
import sys

CONFIG_FILE = 'ffmpeg_config.json'

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def load_config():
    config_path = os.path.join(get_base_path(), CONFIG_FILE)
    default_config = {
        'ffmpeg_path': None,
        'last_codec': 'H.264 (AVC)',
        'default_crf': 23,
        'last_resolution': 'Original',
        'advanced_options': False
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                return {**default_config, **loaded_config}
        except Exception as e:
            print(f"Erro ao carregar config: {e}")
    
    return default_config

def save_config(config):
    config_path = os.path.join(get_base_path(), CONFIG_FILE)
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Erro ao salvar config: {e}")
