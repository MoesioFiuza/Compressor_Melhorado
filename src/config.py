import os
import json
import sys
from typing import Dict, Any, Optional
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = 'ffmpeg_config.json'
_CONFIG_CACHE = None 

DEFAULT_CONFIG: Dict[str, Any] = {
    'ffmpeg_path': None,  # type: Optional[str]
    'last_codec': 'H.264 (AVC)',
    'default_crf': 23,
    'last_resolution': 'Original',
    'advanced_options': False,
    'recent_files': [],  
    'window_geometry': None  # Para lembrar tamanho/posição da janela
}

def get_base_path() -> str:
    """Obtém o caminho base do aplicativo, funcionando para executáveis frozen e desenvolvimento."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Valida e corrige as configurações carregadas."""
    validated = DEFAULT_CONFIG.copy()
    
    # Validação tipo por tipo
    if isinstance(config, dict):
        for key, value in config.items():
            if key in DEFAULT_CONFIG:
                expected_type = type(DEFAULT_CONFIG[key])
                if isinstance(value, expected_type):
                    validated[key] = value
                else:
                    logger.warning(f"Tipo inválido para {key}. Esperado {expected_type}, obtido {type(value)}")
                    # Tenta converter tipos básicos
                    try:
                        if expected_type == int and isinstance(value, str):
                            validated[key] = int(value)
                        elif expected_type == bool and isinstance(value, str):
                            validated[key] = value.lower() in ('true', '1', 't')
                    except (ValueError, AttributeError):
                        logger.error(f"Falha ao converter {key} para {expected_type}")
    
    # Validações específicas
    if validated['ffmpeg_path'] and not os.path.isfile(validated['ffmpeg_path']):
        logger.warning(f"Caminho do FFmpeg inválido: {validated['ffmpeg_path']}")
        validated['ffmpeg_path'] = None
    
    if validated['default_crf'] < 0 or validated['default_crf'] > 51:
        logger.warning(f"Valor CRF inválido: {validated['default_crf']}")
        validated['default_crf'] = DEFAULT_CONFIG['default_crf']
    
    return validated

def load_config(base_path: Optional[str] = None) -> Dict[str, Any]:
    """Carrega a configuração do arquivo com cache."""
    global _CONFIG_CACHE
    
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    
    if base_path is None:
        base_path = get_base_path()
    
    config_path = os.path.join(base_path, CONFIG_FILE)
    loaded_config = DEFAULT_CONFIG.copy()
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                loaded_config.update(file_config)
                
                # Validação adicional para listas
                if 'recent_files' in file_config and isinstance(file_config['recent_files'], list):
                    loaded_config['recent_files'] = [
                        f for f in file_config['recent_files'] 
                        if isinstance(f, str) and os.path.exists(f)
                    ][:10]  # Limita a 10 arquivos recentes
                
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON: {e}")
            # Cria backup do arquivo corrompido
            try:
                backup_path = f"{config_path}.corrupt.{int(time.time())}"
                os.rename(config_path, backup_path)
                logger.error(f"Arquivo de configuração corrompido. Backup criado em: {backup_path}")
            except Exception as backup_error:
                logger.error(f"Falha ao criar backup: {backup_error}")
                
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar config: {e}")
    
    # Aplica validação final
    _CONFIG_CACHE = _validate_config(loaded_config)
    return _CONFIG_CACHE

def save_config(config: Dict[str, Any], base_path: Optional[str] = None) -> bool:
    """Salva a configuração no arquivo e atualiza o cache."""
    global _CONFIG_CACHE
    
    if base_path is None:
        base_path = get_base_path()
    
    config_path = os.path.join(base_path, CONFIG_FILE)
    success = False
    
    # Garante que só salvamos configurações válidas
    validated_config = _validate_config(config)
    
    try:
        # Cria o diretório se não existir
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(validated_config, f, indent=4, ensure_ascii=False)
            _CONFIG_CACHE = validated_config
            success = True
            
    except PermissionError:
        logger.error(f"Sem permissão para escrever em: {config_path}")
        # Tenta um fallback no diretório do usuário
        try:
            fallback_path = os.path.join(os.path.expanduser('~'), CONFIG_FILE)
            with open(fallback_path, 'w', encoding='utf-8') as f:
                json.dump(validated_config, f, indent=4, ensure_ascii=False)
                _CONFIG_CACHE = validated_config
                success = True
                logger.info(f"Config salva em fallback: {fallback_path}")
        except Exception as fallback_error:
            logger.error(f"Falha no fallback: {fallback_error}")
            
    except Exception as e:
        logger.error(f"Erro ao salvar config: {e}")
    
    return success

def clear_cache() -> None:
    """Limpa o cache de configurações (útil para testes)."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None

def get_ffmpeg_path() -> Optional[str]:
    """Helper para obter o caminho do FFmpeg com cache."""
    config = load_config()
    return config.get('ffmpeg_path')

def add_recent_file(file_path: str) -> None:
    """Adiciona um arquivo à lista de recentes."""
    if not os.path.isfile(file_path):
        return
    
    config = load_config()
    recent_files = config.get('recent_files', [])
    
    # Remove duplicatas e mantém apenas os 10 mais recentes
    if file_path in recent_files:
        recent_files.remove(file_path)
    recent_files.insert(0, file_path)
    recent_files = recent_files[:10]
    
    save_config({**config, 'recent_files': recent_files})