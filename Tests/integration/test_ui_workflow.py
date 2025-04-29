import pytest
import sys
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from view import CompressorView

@pytest.fixture
def view(qtbot):
    view = CompressorView()
    qtbot.addWidget(view)
    yield view
    view.close()

def test_select_input_file(view, qtbot, tmp_path):
    test_file = tmp_path / "test.mp4"
    test_file.write_bytes(b"fake video data")
    
    with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(test_file), "")):
        with qtbot.waitSignal(view.select_input_signal):
            view.input_file_selector.button.click()
    
    assert view.get_input_path() == str(test_file)
    assert "test.mp4" in view.video_preview.info_label.text()

def test_quality_buttons(view, qtbot):
    assert view.quality_agg_button.isChecked()
    assert not view.quality_med_button.isChecked()
    assert not view.quality_high_button.isChecked()
    
    qtbot.mouseClick(view.quality_med_button, Qt.LeftButton)
    assert view.quality_med_button.isChecked()
    assert not view.quality_agg_button.isChecked()
    
    qtbot.mouseClick(view.quality_high_button, Qt.LeftButton)
    assert view.quality_high_button.isChecked()
    assert not view.quality_med_button.isChecked()

def test_resolution_combo(view, qtbot):
    assert view.resolution_combo.count() == 5  
    assert view.resolution_combo.currentText() == "480p (SD)"  
    
    view.resolution_combo.setCurrentText("720p (HD)")
    assert view.get_selected_resolution() == "720p (HD)"
    
    view.resolution_combo.setCurrentText("Personalizado...")
    assert view.get_selected_resolution() == "Personalizado..."

def test_advanced_options_toggle(view, qtbot):
    assert not view.advanced_panel.isVisible()
    assert view.advanced_toggle.text() == "Opções Avançadas ▲"  
    
    # Click to show
    qtbot.mouseClick(view.advanced_toggle, Qt.LeftButton)
    assert view.advanced_panel.isVisible()
    assert view.advanced_toggle.text() == "Opções Avançadas ▼"  
    qtbot.mouseClick(view.advanced_toggle, Qt.LeftButton)
    assert not view.advanced_panel.isVisible()
    assert view.advanced_toggle.text() == "Opções Avançadas ▲" 

def test_crf_slider(view, qtbot):
    qtbot.mouseClick(view.advanced_toggle, Qt.LeftButton)
    
    assert view.crf_slider.value() == 23
    
    view.crf_slider.setValue(25)
    assert view.get_crf_value() == 25

def test_start_button_state(view, qtbot, tmp_path):
    assert view.start_button.isEnabled() 
    
    view.set_ffmpeg_path("fake_ffmpeg")
    assert view.start_button.isEnabled()
    
    test_file = tmp_path / "input.mp4"
    test_file.write_bytes(b"fake data")
    view.set_input_path(str(test_file))
    assert view.start_button.isEnabled()
    
    output_file = tmp_path / "output.mp4"
    view.set_output_path(str(output_file))
    assert view.start_button.isEnabled()
    
    view.set_input_path("")
    assert not view.start_button.isEnabled()

def test_log_messages(view, qtbot):
    test_message = "Test message"
    
    assert view.log_area.toPlainText() == ""
    
    view.log_message(test_message)
    assert test_message in view.log_area.toPlainText()
    
    view.clear_log()
    assert view.log_area.toPlainText() == ""
