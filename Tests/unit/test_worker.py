import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QObject, Signal
from subprocess import TimeoutExpired

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))
from worker import CompressionWorker

@pytest.fixture
def worker():
    return CompressionWorker(
        ffmpeg_path="fake_ffmpeg",
        input_file="fake_input.mp4",
        output_file="fake_output.mp4"
    )

@pytest.fixture
def real_worker(tmp_path):
    input_file = tmp_path / "input.mp4"
    output_file = tmp_path / "output.mp4"
    input_file.write_bytes(b"fake video data")
    return CompressionWorker(
        ffmpeg_path="fake_ffmpeg",
        input_file=str(input_file),
        output_file=str(output_file)
    )

def test_worker_initialization(worker):
    assert isinstance(worker, QObject)
    assert worker.ffmpeg_path == "fake_ffmpeg"
    assert worker.input_file == "fake_input.mp4"
    assert worker.output_file == "fake_output.mp4"
    assert worker._is_running is True
    assert worker.process is None

def test_worker_stop(worker):
    worker.process = MagicMock()
    worker.process.poll.return_value = None  # Simula processo em execução
    worker.stop()
    assert worker._is_running is False
    worker.process.terminate.assert_called_once()

def test_worker_stop_with_kill(worker):
    worker.process = MagicMock()
    worker.process.poll.side_effect = [None, None]
    worker.process.wait.side_effect = TimeoutExpired(cmd='ffmpeg', timeout=1.0)
    worker.stop()
    assert worker.process.terminate.called
    assert worker.process.kill.called

@patch('os.path.isfile', return_value=True)
@patch('subprocess.Popen')
@patch('worker.CompressionWorker._get_video_info')
def test_run_successful(mock_get_info, mock_popen, mock_isfile, worker):
    mock_get_info.return_value = (10, 1920, 1080, 30)
    mock_proc = MagicMock()
    mock_proc.stderr.readline.side_effect = ["time=00:00:01.00", "time=00:00:02.00", ""]
    mock_proc.poll.return_value = 0
    mock_proc.returncode = 0  # Adicionado para simular sucesso
    mock_popen.return_value = mock_proc

    worker.run()
    assert mock_popen.called
    assert worker.process == mock_proc
    mock_proc.stderr.readline.assert_called()

@patch('os.path.isfile', return_value=True)
@patch('subprocess.Popen')
@patch('worker.CompressionWorker._get_video_info')
def test_run_with_stop_signal(mock_get_info, mock_popen, mock_isfile, worker):
    mock_get_info.return_value = (10, 1920, 1080, 30)
    worker._is_running = False
    worker.run()
    assert not mock_popen.called

@patch('os.path.isfile', return_value=True)
@patch('subprocess.Popen')
@patch('worker.CompressionWorker._get_video_info')
def test_run_with_ffmpeg_error(mock_get_info, mock_popen, mock_isfile, worker):
    mock_get_info.return_value = (10, 1920, 1080, 30)
    mock_proc = MagicMock()
    mock_proc.stderr.readline.side_effect = ["time=00:00:01.00", "[error] Something went wrong", ""]
    mock_proc.poll.return_value = 1
    mock_proc.returncode = 1  # Adicionado para simular erro
    mock_popen.return_value = mock_proc

    worker.run()
    assert mock_proc.poll() == 1

@patch('os.path.isfile', return_value=True)
@patch('subprocess.Popen')
@patch('worker.CompressionWorker._get_video_info')
def test_run_with_missing_input_file(mock_get_info, mock_popen, mock_isfile, worker):
    mock_get_info.return_value = (None, None, None, None)
    worker.run()
    assert not mock_popen.called

@patch('os.path.exists', return_value=True)
@patch('os.path.getsize')
@patch('os.path.isfile', return_value=True)
@patch('subprocess.Popen')
@patch('worker.CompressionWorker._get_video_info')
def test_run_with_size_comparison(mock_get_info, mock_popen, mock_isfile, mock_getsize, mock_exists, worker):
    mock_get_info.return_value = (30, 1920, 1080, 30)
    mock_proc = MagicMock()
    mock_proc.stderr.readline.side_effect = ["time=00:00:01.00", ""]
    mock_proc.poll.return_value = 0
    mock_proc.returncode = 0  # Garante que o processo terminou com sucesso
    mock_popen.return_value = mock_proc
    
    # Configura o mock para simular:
    # 1ª chamada: tamanho do arquivo original (100MB)
    # 2ª chamada: tamanho do arquivo comprimido (30MB)
    mock_getsize.side_effect = [100 * 1024 * 1024, 30 * 1024 * 1024]
    
    # Configura exists() para retornar True especificamente para o arquivo de saída
    def exists_side_effect(path):
        if path == worker.output_file:
            return True
        return False  # Padrão para outros paths
    
    mock_exists.side_effect = exists_side_effect
    
    worker.run()
    
    # Verifica se getsize foi chamado 2 vezes
    assert mock_getsize.call_count == 2
    # Verifica se foi chamado primeiro com input_file e depois com output_file
    assert mock_getsize.call_args_list[0][0][0] == worker.input_file
    assert mock_getsize.call_args_list[1][0][0] == worker.output_file

def test_get_video_info_success(worker):
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.stderr = (
            "Duration: 00:01:30.50\n"
            "Stream #0:0: Video: h264, 1280x720, 25 fps\n"
            "Stream #0:1: Audio: aac"
        )
        duration, width, height, fps = worker._get_video_info()
        assert duration == 90.5
        assert width == 1280
        assert height == 720
        assert fps == 25.0

def test_get_video_info_failure(worker):
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = FileNotFoundError("FFmpeg not found")
        result = worker._get_video_info()
        assert result == (None, None, None, None)

def test_worker_signals(worker):
    assert hasattr(worker, 'progress_updated')
    assert hasattr(worker, 'status_message')
    assert hasattr(worker, 'finished')
    assert hasattr(worker, 'error_occurred')
    assert isinstance(worker.progress_updated, type(Signal()))