import os
import sys
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLineEdit, QLabel, QFileDialog,
                               QMessageBox, QProgressBar, QTextEdit, QGroupBox,
                               QSizePolicy, QFormLayout, QComboBox, QButtonGroup) # Added QComboBox, QButtonGroup
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCloseEvent

class PathSelector(QtWidgets.QWidget):
    path_selected = QtCore.Signal(str)

    SELECT_FILE = 0
    SELECT_DIRECTORY = 1
    SAVE_FILE = 2

    def __init__(self, selector_type=SELECT_FILE, dialog_title="Selecionar Arquivo", file_filter="Todos os Arquivos (*.*)", parent=None):
        super().__init__(parent)
        self._selector_type = selector_type
        self._dialog_title = dialog_title
        self._file_filter = file_filter
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(5)
        self.line_edit = QtWidgets.QLineEdit()
        self.button = QtWidgets.QPushButton("...")
        self.button.setFixedWidth(35)
        self.button.setToolTip("Selecionar caminho...")
        self._layout.addWidget(self.line_edit)
        self._layout.addWidget(self.button)
        self.button.clicked.connect(self._open_dialog)

    def set_options(self, selector_type=None, dialog_title=None, file_filter=None):
        if selector_type is not None: self._selector_type = selector_type
        if dialog_title is not None: self._dialog_title = dialog_title
        if file_filter is not None: self._file_filter = file_filter

    @QtCore.Slot()
    def _open_dialog(self):
        current_path = self.get_path()
        initial_dir = os.path.dirname(current_path) if current_path and (self._selector_type != self.SELECT_DIRECTORY or os.path.isfile(current_path)) \
                      else current_path if current_path and self._selector_type == self.SELECT_DIRECTORY and os.path.isdir(current_path) \
                      else os.path.expanduser("~")

        selected_path = None
        if self._selector_type == self.SELECT_FILE:
            selected_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, self._dialog_title, initial_dir, self._file_filter)
        elif self._selector_type == self.SELECT_DIRECTORY:
            selected_path = QtWidgets.QFileDialog.getExistingDirectory(self, self._dialog_title, initial_dir)
        elif self._selector_type == self.SAVE_FILE:
             default_name = os.path.basename(current_path) if current_path else ""
             selected_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, self._dialog_title, os.path.join(initial_dir, default_name), self._file_filter)

        if selected_path:
            if self._selector_type == self.SAVE_FILE and "*" in self._file_filter:
                 default_ext = ".mp4"
                 if "." not in os.path.basename(selected_path):
                     try:
                         start = self._file_filter.find("(*") + 2
                         end = self._file_filter.find(")", start)
                         ext = self._file_filter[start:end].split()[0]
                         if ext and ext != ".*": default_ext = ext.strip()
                     except Exception: pass
                     if not selected_path.lower().endswith(default_ext): selected_path += default_ext
            self.set_path(selected_path)
            self.path_selected.emit(selected_path)

    def get_path(self): return self.line_edit.text()
    def set_path(self, path): self.line_edit.setText(path)
    def setReadOnly(self, readonly): self.line_edit.setReadOnly(readonly)
    def setPlaceholderText(self, text): self.line_edit.setPlaceholderText(text)


class LogWidget(QtWidgets.QTextEdit):
    INFO = "INFO"; WARN = "AVISO"; ERROR = "ERRO"; CMD = "CMD"; FFMPEG = "FFMPEG"
    LOG_COLORS = { INFO: "#000000", WARN: "#FFA500", ERROR: "#FF0000", CMD: "#0000FF", FFMPEG: "#696969" }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.NoWrap)

    @QtCore.Slot(str, str)
    def append_message(self, text, level=INFO):
        color = self.LOG_COLORS.get(level.upper(), self.LOG_COLORS[self.INFO])
        escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        formatted_message = f'<pre style="color:{color}; margin:0; padding:0;">{escaped_text}</pre>'
        self.append(formatted_message)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_log(self): self.clear()


class CompressorView(QWidget):
    start_compression_signal = Signal(str, str, str)
    stop_compression_signal = Signal()
    select_ffmpeg_signal = Signal()
    select_input_signal = Signal()
    select_output_signal = Signal()
    closing = Signal()

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Compressor de Vídeo Aggressive')
        self.setGeometry(200, 200, 650, 600) # Increased height for quality options

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self._setup_ffmpeg_group(main_layout)
        self._setup_files_group(main_layout)
        self._setup_quality_buttons_group(main_layout) # Use buttons group
        self._setup_progress_group(main_layout)
        self._setup_log_group(main_layout)

    def _setup_ffmpeg_group(self, main_layout):
        config_group = QGroupBox("Configuração do FFmpeg")
        config_layout = QHBoxLayout(config_group)
        self.ffmpeg_path_selector = PathSelector(selector_type=PathSelector.SELECT_FILE,
                                                 dialog_title="Selecionar FFmpeg",
                                                 file_filter="Executável FFmpeg (ffmpeg*);;Todos (*)")
        self.ffmpeg_path_selector.setPlaceholderText("Caminho para ffmpeg.exe")
        self.ffmpeg_path_selector.setReadOnly(True)
        self.ffmpeg_path_selector.button.clicked.connect(self.select_ffmpeg_signal.emit)
        config_layout.addWidget(self.ffmpeg_path_selector)
        main_layout.addWidget(config_group)

    def _setup_files_group(self, main_layout):
        files_group = QGroupBox("Seleção de Arquivos")
        files_form_layout = QFormLayout(files_group)
        self.input_file_selector = PathSelector(selector_type=PathSelector.SELECT_FILE,
                                                dialog_title="Selecionar Vídeo de Entrada",
                                                file_filter="Vídeos (*.mp4 *.avi *.mov *.mkv *.webm *.flv);;Todos (*.*)")
        self.input_file_selector.setPlaceholderText("Selecione o vídeo original")
        self.input_file_selector.button.clicked.connect(self.select_input_signal.emit)
        files_form_layout.addRow("Arquivo de Entrada:", self.input_file_selector)
        self.output_file_selector = PathSelector(selector_type=PathSelector.SAVE_FILE,
                                                 dialog_title="Salvar Vídeo Comprimido Como",
                                                 file_filter="Vídeo MP4 (*.mp4)")
        self.output_file_selector.setPlaceholderText("Onde salvar o vídeo comprimido")
        self.output_file_selector.button.clicked.connect(self.select_output_signal.emit)
        files_form_layout.addRow("Arquivo de Saída:", self.output_file_selector)
        main_layout.addWidget(files_group)

    def _setup_quality_buttons_group(self, main_layout):
        quality_group = QGroupBox("Qualidade da Compressão")
        quality_layout = QHBoxLayout(quality_group)
        self.quality_button_group = QButtonGroup(self)
        self.quality_button_group.setExclusive(True)

        self.quality_agg_button = QPushButton("Agressiva")
        self.quality_agg_button.setCheckable(True)
        self.quality_agg_button.setToolTip("Foco em reduzir tamanho, pode perder qualidade.")
        quality_layout.addWidget(self.quality_agg_button)
        self.quality_button_group.addButton(self.quality_agg_button)

        self.quality_med_button = QPushButton("Média")
        self.quality_med_button.setCheckable(True)
        self.quality_med_button.setToolTip("Bom equilíbrio entre tamanho e qualidade.")
        quality_layout.addWidget(self.quality_med_button)
        self.quality_button_group.addButton(self.quality_med_button)

        self.quality_high_button = QPushButton("Alta")
        self.quality_high_button.setCheckable(True)
        self.quality_high_button.setToolTip("Prioriza qualidade visual, arquivos maiores.")
        quality_layout.addWidget(self.quality_high_button)
        self.quality_button_group.addButton(self.quality_high_button)

        self.quality_agg_button.setChecked(True)
        quality_layout.addStretch()
        main_layout.addWidget(quality_group)

    def _setup_progress_group(self, main_layout):
        progress_group = QGroupBox("Progresso e Controle")
        progress_layout = QVBoxLayout(progress_group)
        progress_bar_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setValue(0)
        self.eta_label = QLabel("ETA: --:--")
        eta_font = self.eta_label.font(); eta_font.setPointSize(eta_font.pointSize() + 1); eta_font.setBold(True)
        self.eta_label.setFont(eta_font); self.eta_label.setMinimumWidth(80); self.eta_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        progress_bar_layout.addWidget(self.progress_bar)
        progress_bar_layout.addWidget(self.eta_label)
        progress_layout.addLayout(progress_bar_layout)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.start_button = QPushButton(" Iniciar Compressão")
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button = QPushButton(" Parar")
        self.stop_button.clicked.connect(self.stop_compression_signal.emit)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()
        progress_layout.addLayout(button_layout)
        main_layout.addWidget(progress_group)

    def _setup_log_group(self, main_layout):
        log_group = QGroupBox("Log de Eventos")
        log_layout = QVBoxLayout(log_group)
        self.log_area = LogWidget()
        log_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_area.setSizePolicy(log_policy)
        log_layout.addWidget(self.log_area)
        main_layout.addWidget(log_group)
        log_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _on_start_clicked(self):
        self.start_compression_signal.emit(
            self.ffmpeg_path_selector.get_path(),
            self.input_file_selector.get_path(),
            self.output_file_selector.get_path()
        )

    def get_ffmpeg_path(self): return self.ffmpeg_path_selector.get_path()
    def get_input_path(self): return self.input_file_selector.get_path()
    def get_output_path(self): return self.output_file_selector.get_path()

    def set_ffmpeg_path(self, path): self.ffmpeg_path_selector.set_path(path)
    def set_input_path(self, path): self.input_file_selector.set_path(path)
    def set_output_path(self, path): self.output_file_selector.set_path(path)

    def get_selected_quality(self):
        checked_button = self.quality_button_group.checkedButton()
        if checked_button:
            button_text = checked_button.text()
            if button_text == "Agressiva":
                return "Agressiva (Menor Arquivo)"
            elif button_text == "Média":
                return "Média (Balanceado)"
            elif button_text == "Alta":
                return "Alta (Melhor Qualidade)"
            else:
                return button_text
        else:
            print("AVISO: Nenhum botão de qualidade está selecionado!")
            return "Agressiva (Menor Arquivo)"

    def update_progress(self, percent, eta_str):
        self.progress_bar.setValue(percent)
        self.eta_label.setText(eta_str)

    def reset_progress(self):
        self.progress_bar.setValue(0)
        self.eta_label.setText("ETA: --:--")

    def set_ui_busy(self, busy):
        is_ready_to_start = bool(self.get_ffmpeg_path() and self.get_input_path() and self.get_output_path())
        self.start_button.setEnabled(not busy and is_ready_to_start)
        self.stop_button.setEnabled(busy)
        self.ffmpeg_path_selector.setEnabled(not busy)
        self.input_file_selector.setEnabled(not busy)
        self.output_file_selector.setEnabled(not busy)
        self.quality_agg_button.setEnabled(not busy)
        self.quality_med_button.setEnabled(not busy)
        self.quality_high_button.setEnabled(not busy)

    def log_message(self, message, level=LogWidget.INFO):
        self.log_area.append_message(message, level)

    def clear_log(self):
        self.log_area.clear_log()

    def show_error_message(self, title, message):
        QMessageBox.critical(self, title, message)
        self.log_message(f"{message}", LogWidget.ERROR)

    def show_success_message(self, title, message):
        QMessageBox.information(self, title, message)

    def show_warning_message(self, title, message):
         QMessageBox.warning(self, title, message)

    def confirm_exit_dialog(self):
        return QMessageBox.question(
            self, 'Sair?',
            'A compressão ainda está em andamento.\nDeseja parar o processo e sair?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes

    def closeEvent(self, event: QCloseEvent):
        self.closing.emit()
        event.ignore()