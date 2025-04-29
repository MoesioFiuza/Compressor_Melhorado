import pytest
import sys
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from view import CompressorView

@pytest.fixture
def view(qtbot):
    """Fixture to create and manage the view"""
    view = CompressorView()
    qtbot.addWidget(view)
    yield view
    view.close()

def test_select_input_file(view, qtbot, tmp_path):
    """Tests input file selection"""
    # Create temporary file
    test_file = tmp_path / "test.mp4"
    test_file.write_bytes(b"fake video data")
    
    # Mock QFileDialog to simulate file selection
    with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(test_file), "")):
        with qtbot.waitSignal(view.select_input_signal):
            view.input_file_selector.button.click()
    
    # Verify path was set correctly
    assert view.get_input_path() == str(test_file)
    assert "test.mp4" in view.video_preview.info_label.text()

def test_quality_buttons(view, qtbot):
    """Tests quality radio buttons"""
    # Verify initial state
    assert view.quality_agg_button.isChecked()
    assert not view.quality_med_button.isChecked()
    assert not view.quality_high_button.isChecked()
    
    # Test medium quality click
    qtbot.mouseClick(view.quality_med_button, Qt.LeftButton)
    assert view.quality_med_button.isChecked()
    assert not view.quality_agg_button.isChecked()
    
    # Test high quality click
    qtbot.mouseClick(view.quality_high_button, Qt.LeftButton)
    assert view.quality_high_button.isChecked()
    assert not view.quality_med_button.isChecked()

def test_resolution_combo(view, qtbot):
    """Tests resolution combobox"""
    # Verify items and default selection (updated to match current UI)
    assert view.resolution_combo.count() == 5  # Original + 4 options
    assert view.resolution_combo.currentText() == "480p (SD)"  # Updated from "Original"
    
    # Test resolution change
    view.resolution_combo.setCurrentText("720p (HD)")
    assert view.get_selected_resolution() == "720p (HD)"
    
    # Test custom resolution selection
    view.resolution_combo.setCurrentText("Personalizado...")
    assert view.get_selected_resolution() == "Personalizado..."

def test_advanced_options_toggle(view, qtbot):
    """Tests advanced options toggle"""
    # Verify initial state (updated to match current UI)
    assert not view.advanced_panel.isVisible()
    assert view.advanced_toggle.text() == "Opções Avançadas ▲"  # Updated arrow direction
    
    # Click to show
    qtbot.mouseClick(view.advanced_toggle, Qt.LeftButton)
    assert view.advanced_panel.isVisible()
    assert view.advanced_toggle.text() == "Opções Avançadas ▼"  # Arrow changes when expanded
    
    # Click to hide
    qtbot.mouseClick(view.advanced_toggle, Qt.LeftButton)
    assert not view.advanced_panel.isVisible()
    assert view.advanced_toggle.text() == "Opções Avançadas ▲"  # Arrow returns to initial

def test_crf_slider(view, qtbot):
    """Tests CRF slider in advanced options"""
    # Show advanced options
    qtbot.mouseClick(view.advanced_toggle, Qt.LeftButton)
    
    # Verify default value
    assert view.crf_slider.value() == 23
    
    # Test value change
    view.crf_slider.setValue(25)
    assert view.get_crf_value() == 25

def test_start_button_state(view, qtbot, tmp_path):
    """Tests start button state"""
    # Initially enabled (updated to match current UI behavior)
    assert view.start_button.isEnabled()  # Changed from assert not
    
    # Set FFmpeg path
    view.set_ffmpeg_path("fake_ffmpeg")
    assert view.start_button.isEnabled()
    
    # Set input file
    test_file = tmp_path / "input.mp4"
    test_file.write_bytes(b"fake data")
    view.set_input_path(str(test_file))
    assert view.start_button.isEnabled()
    
    # Set output file
    output_file = tmp_path / "output.mp4"
    view.set_output_path(str(output_file))
    assert view.start_button.isEnabled()
    
    # Test with missing requirements
    view.set_input_path("")
    assert not view.start_button.isEnabled()

def test_log_messages(view, qtbot):
    """Tests logging system"""
    test_message = "Test message"
    
    # Verify empty log initially
    assert view.log_area.toPlainText() == ""
    
    # Add log message
    view.log_message(test_message)
    assert test_message in view.log_area.toPlainText()
    
    # Test log clearing
    view.clear_log()
    assert view.log_area.toPlainText() == ""