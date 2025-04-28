import os
import json
import sys

CONFIG_FILE = 'ffmpeg_config.json'

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def load_ffmpeg_path():
    config_path = os.path.join(get_base_path(), CONFIG_FILE)
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                candidate_path = config.get('ffmpeg_path')
                if candidate_path and os.path.isfile(candidate_path):
                    return candidate_path
        except Exception as e:
            print(f"Erro ao carregar config '{config_path}': {e}")
            pass
    return None

def save_ffmpeg_path(path):
    config_path = os.path.join(get_base_path(), CONFIG_FILE)
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump({'ffmpeg_path': path}, f, indent=4)
    except Exception as e:
        print(f"Erro ao salvar config '{config_path}': {e}")
        pass