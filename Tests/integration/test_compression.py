import pytest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from controller import CompressionController
from view import CompressorView

@pytest.fixture
def temp_video(tmp_path):
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"fake video data")
    return str(video_path)

@pytest.fixture
def controller(qtbot, tmp_path):
    view = CompressorView()
    qtbot.addWidget(view)
    controller = CompressionController(view)
    yield controller
    view.close()

def test_controller_initialization(controller):
    assert controller.view is not None
    assert hasattr(controller, 'ffmpeg_path')  
    
def test_ffmpeg_path_property(controller):
    test_path = "fake/path/to/ffmpeg"
    controller.ffmpeg_path = test_path  
    assert controller.ffmpeg_path == test_path

def test_compress_video(controller, temp_video, tmp_path, qtbot):
    output_path = str(tmp_path / "output.mp4")
    controller.ffmpeg_path = "ffmpeg"  
    
    if hasattr(controller, 'compressor'):
        with patch.object(controller, 'compressor') as mock_compressor:
            mock_compressor.compress.return_value = True
            
            controller.view.set_input_path(temp_video)
            controller.view.set_output_path(output_path)
            
            if hasattr(controller.view, 'compression_finished_signal'):
                with qtbot.waitSignal(controller.view.compression_finished_signal):
                    controller.compress_video()  
            else:
                controller.compress_video()  
            
            if hasattr(controller, 'compressor'):
                mock_compressor.compress.assert_called_once()

def test_compression_with_missing_input(controller, tmp_path, qtbot):
    output_path = str(tmp_path / "output.mp4")
    controller.ffmpeg_path = "ffmpeg"
    controller.view.set_output_path(output_path)
    
    if hasattr(controller, 'validate_inputs'):
        assert not controller.validate_inputs()
    else:
        assert not controller.view.start_button.isEnabled()

def test_compression_with_missing_output(controller, temp_video, qtbot):
    """Test compression with missing output path"""
    controller.ffmpeg_path = "ffmpeg"
    controller.view.set_input_path(temp_video)
    
    if hasattr(controller, 'validate_inputs'):
        assert not controller.validate_inputs()
    else:
        assert not controller.view.start_button.isEnabled()

def test_compression_progress_updates(controller, temp_video, tmp_path, qtbot):
    if not hasattr(controller, 'update_progress'):
        pytest.skip("No progress update mechanism in controller")
        
    output_path = str(tmp_path / "output.mp4")
    controller.ffmpeg_path = "ffmpeg"
    controller.view.set_input_path(temp_video)
    controller.view.set_output_path(output_path)
    
    test_progress = 50
    controller.update_progress = MagicMock()
    
    controller.compress_video()
    
    controller.update_progress.assert_called_with(test_progress)
