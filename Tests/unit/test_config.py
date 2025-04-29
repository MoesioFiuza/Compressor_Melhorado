import os
import json
from pathlib import Path
import pytest
from unittest.mock import patch

import sys
from pathlib import Path


sys.path.append(str(Path(__file__).parent.parent.parent / "src"))


from config import load_config, save_config, CONFIG_FILE



def test_load_config_default(tmp_path):
    """Testa o carregamento da configuração padrão quando não existe arquivo"""
    config = load_config(base_path=tmp_path)
    assert config['ffmpeg_path'] is None
    assert config['last_codec'] == 'H.264 (AVC)'
    assert config['default_crf'] == 23
    assert config['last_resolution'] == 'Original'
    assert config['advanced_options'] is False

def test_save_and_load_config(tmp_path):
    """Testa o ciclo completo de salvar e carregar configurações"""
    test_config = {
        'ffmpeg_path': '/caminho/para/ffmpeg',
        'last_codec': 'VP9',
        'default_crf': 25,
        'last_resolution': '720p (HD)',
        'advanced_options': True
    }
    save_config(test_config, base_path=tmp_path)
    config_file = tmp_path / CONFIG_FILE
    assert config_file.exists()
    loaded = load_config(base_path=tmp_path)
    for k, v in test_config.items():
        assert loaded[k] == v

def test_save_config_with_invalid_path(tmp_path, capsys):
    """Testa tratamento de erro ao salvar em caminho inválido"""

    dummypath = tmp_path / "nao_existe"
    with patch("builtins.open", side_effect=PermissionError("Sem permissão")):
        save_config({'foo': 'bar'}, base_path=dummypath)
    capt = capsys.readouterr()
    assert "Erro ao salvar config: Sem permissão" in capt.out

def test_load_config_corrupted_file(tmp_path):
    """Testa carregamento de arquivo corrompido"""
    config_file = tmp_path / CONFIG_FILE
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write("{invalid json}")
    config = load_config(base_path=tmp_path)
    # Deve devolver o padrão!
    assert config['ffmpeg_path'] is None
    assert config['last_codec'] == 'H.264 (AVC)'
    assert config['default_crf'] == 23

def test_load_config_merges_with_default(tmp_path):
    """Testa se faltantes no config file vem do padrão"""
    config_file = tmp_path / CONFIG_FILE
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump({'ffmpeg_path': '/ffmpeg'}, f)
    config = load_config(base_path=tmp_path)
    assert config['ffmpeg_path'] == '/ffmpeg'
    assert config['last_codec'] == 'H.264 (AVC)'

def test_load_config_custom_fields(tmp_path):
    """Testa se campos desconhecidos são mantidos"""
    config_file = tmp_path / CONFIG_FILE
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump({'foo': 567, 'last_codec': 'VP9'}, f)
    config = load_config(base_path=tmp_path)
    assert config['foo'] == 567
    assert config['last_codec'] == 'VP9'

def test_save_config_overwrites(tmp_path):
    """Testa se sobrescreve arquivo existente corretamente"""
    config_file = tmp_path / CONFIG_FILE
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump({'ffmpeg_path': 'antigo'}, f)
    test_config = {
        'ffmpeg_path': '/novo/ffmpeg',
        'last_codec': 'H.265 (HEVC)',
        'default_crf': 12,
        'last_resolution': '1080p (Full HD)',
        'advanced_options': False
    }
    save_config(test_config, base_path=tmp_path)
    loaded = load_config(base_path=tmp_path)
    for k, v in test_config.items():
        assert loaded[k] == v
