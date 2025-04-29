import os
import sys
import tempfile
import subprocess
import time
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLineEdit, QLabel, QFileDialog,
                               QMessageBox, QProgressBar, QTextEdit, QGroupBox,
                               QSizePolicy, QFormLayout, QComboBox, QButtonGroup,
                               QScrollArea, QSlider)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QCloseEvent, QPixmap, QPainter
from config import load_config, save_config


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
        self.line_edit.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                background: white;
            }
            QLineEdit:disabled {
                background: #f5f5f5;
            }
        """)
        
        self.button = QtWidgets.QPushButton("...")
        self.button.setFixedWidth(35)
        self.button.setToolTip("Selecionar caminho...")
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #5c9eed;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #4d8fd6;
            }
            QPushButton:pressed {
                background-color: #3a7fc1;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self._layout.addWidget(self.line_edit)
        self._layout.addWidget(self.button)
        self.button.clicked.connect(self._open_dialog)
        
        self.setAcceptDrops(True)
        self.line_edit.setAcceptDrops(False)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                path = urls[0].toLocalFile()
                if ((self._selector_type == self.SELECT_FILE and os.path.isfile(path)) or
                   (self._selector_type == self.SELECT_DIRECTORY and os.path.isdir(path))):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if ((self._selector_type == self.SELECT_FILE and os.path.isfile(path)) or
               (self._selector_type == self.SELECT_DIRECTORY and os.path.isdir(path))):
                self.set_path(path)
                self.path_selected.emit(path)

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


class VideoPreview(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setStyleSheet("""
            background-color: #222222;
            border: 1px solid #444444;
            border-radius: 4px;
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)
        
        self.info_label = QLabel("Arraste um vídeo aqui ou selecione abaixo")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("""
            color: #aaaaaa;
            font-size: 12px;
            padding: 5px;
        """)
        self.layout.addWidget(self.info_label)
        
        self.thumbnail_container = QWidget()
        self.thumbnail_container.setStyleSheet("background-color: transparent;")
        self.thumbnail_layout = QVBoxLayout(self.thumbnail_container)
        self.thumbnail_layout.setContentsMargins(0, 0, 0, 0)
        
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_layout.addWidget(self.thumbnail_label)
        
        self.layout.addWidget(self.thumbnail_container, 1)
        
        self.metadata_label = QLabel()
        self.metadata_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.metadata_label.setStyleSheet("""
            color: #cccccc;
            font-size: 10px;
        """)
        self.layout.addWidget(self.metadata_label)

    def set_video(self, path):
        if not path or not os.path.isfile(path):
            self.clear()
            return
            
        try:
            self.info_label.setText(os.path.basename(path))
        except Exception as e:
            print(f"Error setting video info label: {str(e)}")
            
            temp_dir = tempfile.gettempdir()
            thumb_name = f"thumb_{os.path.splitext(os.path.basename(path))[0]}.jpg"
            thumbnail_path = os.path.join(temp_dir, thumb_name)
            
            cmd = [
                "ffmpeg", "-y", "-i", path,
                "-ss", "00:00:01", "-vframes", "1",
                "-vf", "scale=400:-1",
                thumbnail_path
            ]
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            subprocess.run(cmd, startupinfo=startupinfo, stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, check=True)
            
            if os.path.exists(thumbnail_path):
                pixmap = QPixmap(thumbnail_path)
                if not pixmap.isNull():
                    self.thumbnail_label.setPixmap(
                        pixmap.scaled(self.thumbnail_container.width(), 
                                      self.thumbnail_container.height(),
                                      Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation))
            
            duration = self._get_video_duration(path)
            if duration > 0:
                self.metadata_label.setText(
                    f"Duração: {time.strftime('%H:%M:%S', time.gmtime(duration))}"
                )
            
        except subprocess.CalledProcessError as e:
            self.clear()
            print(f"Erro ao gerar thumbnail: {e.stderr.decode()}")
        except Exception as e:
            self.clear()
            print(f"Erro inesperado: {str(e)}")

    def _get_video_duration(self, path):
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return float(result.stdout.strip())
        except:
            return 0

    def clear(self):
        self.thumbnail_label.clear()
        self.metadata_label.clear()
        self.info_label.setText("Arraste um vídeo aqui ou selecione abaixo")
        self.info_label.setStyleSheet("""
            color: #aaaaaa;
            font-size: 12px;
            padding: 5px;
        """)

    def resizeEvent(self, event):
        if hasattr(self.thumbnail_label, 'pixmap') and self.thumbnail_label.pixmap():
            self.thumbnail_label.setPixmap(
                self.thumbnail_label.pixmap().scaled(
                    self.thumbnail_container.width(),
                    self.thumbnail_container.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
        super().resizeEvent(event)


class SizeComparisonChart(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(100)
        self.original_size = 0
        self.compressed_size = 0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        
        painter.fillRect(self.rect(), QtGui.QColor("#f8f8f8"))
        
        if self.original_size > 0:
            max_width = self.width() - 40
            margin = 20
            
            painter.setPen(QtGui.QColor("#cccccc"))
            painter.setBrush(QtGui.QColor("#ffffff"))
            painter.drawRoundedRect(margin, 10, max_width, 70, 5, 5)
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor("#e0e0e0"))
            painter.drawRoundedRect(margin + 2, 30, max_width - 4, 20, 3, 3)
            
            if self.compressed_size > 0:
                compressed_width = max(10, int((self.compressed_size / self.original_size) * (max_width - 4)))
                painter.setBrush(QtGui.QColor("#5c9eed"))
                painter.drawRoundedRect(margin + 2, 55, compressed_width, 20, 3, 3)
            
            painter.setPen(QtGui.QColor("#333333"))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            
            original_text = f"Original: {self.original_size:.2f} MB"
            painter.drawText(margin + 5, 25, original_text)
            
            if self.compressed_size > 0:
                reduction = 100 - (self.compressed_size / self.original_size * 100)
                compressed_text = f"Comprimido: {self.compressed_size:.2f} MB ({reduction:.1f}% menor)"
                painter.drawText(margin + 5, 50, compressed_text)
            
            if self.compressed_size > 0:
                painter.setPen(QtGui.QPen(QtGui.QColor("#ff5722"), 1, Qt.PenStyle.DotLine))
                y_pos = 47
                painter.drawLine(margin + 2 + compressed_width, y_pos, margin + max_width - 2, y_pos)
    
    def update_sizes(self, original, compressed):
        self.original_size = original
        self.compressed_size = compressed
        self.update()


class LogWidget(QtWidgets.QTextEdit):
    INFO = "INFO"; WARN = "AVISO"; ERROR = "ERRO"; CMD = "CMD"; FFMPEG = "FFMPEG"
    LOG_COLORS = { INFO: "#000000", WARN: "#FFA500", ERROR: "#FF0000", CMD: "#0000FF", FFMPEG: "#696969" }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.NoWrap)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #f8f8f8;
                border: 1px solid #dddddd;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
            }
        """)

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
        self.setWindowTitle('Compressor de Vídeo Aggressive')
        self.setMinimumSize(800, 600)
        
        # Configuração da área de rolagem
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Widget que contém todo o conteúdo
        self.content = QWidget()
        self.scroll.setWidget(self.content)
        
        # Layout do conteúdo
        self.layout = QVBoxLayout(self.content)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(15, 15, 15, 15)
        
        # Configura o layout da janela principal
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.scroll)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.init_ui()
        self.setup_styles()
        self.load_settings()

    def load_settings(self):
        config = load_config()
        self.advanced_toggle.setChecked(config.get('advanced_options', False))
        self._toggle_advanced_options(config['advanced_options'])
        self.codec_combo.setCurrentText(config['last_codec'])
        self.resolution_combo.setCurrentText(config['last_resolution'])

    def save_settings(self):
        save_config({
            'ffmpeg_path': self.get_ffmpeg_path(),
            'last_codec': self.get_selected_codec(),
            'last_resolution': self.get_selected_resolution(),
            'advanced_options': self.advanced_toggle.isChecked()
        })

    def init_ui(self):
        self._setup_ffmpeg_group()
        self._setup_files_group()
        self._setup_preview_group()
        self._setup_quality_buttons_group()
        self._setup_progress_group()
        self._setup_log_group()

    def setup_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #333333;
            }
            
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #dddddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: white;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #555555;
            }
            
            QPushButton {
                background-color: #5c9eed;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                min-width: 80px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #4d8fd6;
            }
            
            QPushButton:pressed {
                background-color: #3a7fc1;
            }
            
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
            
            QProgressBar {
                border: 1px solid #cccccc;
                border-radius: 4px;
                text-align: center;
                background: white;
            }
            
            QProgressBar::chunk {
                background-color: #5c9eed;
                width: 10px;
            }
            
            QLabel {
                color: #555555;
            }
            
            #etaLabel {
                font-weight: bold;
                color: #333333;
            }
            
            QScrollArea {
                border: none;
            }
            
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 12px;
                margin: 0px 0px 0px 0px;
            }
            
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                min-height: 20px;
                border-radius: 6px;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def _setup_ffmpeg_group(self):
        config_group = QGroupBox("Configuração do FFmpeg")
        config_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        config_layout = QHBoxLayout(config_group)
        
        self.ffmpeg_path_selector = PathSelector(
            selector_type=PathSelector.SELECT_FILE,
            dialog_title="Selecionar FFmpeg",
            file_filter="Executável FFmpeg (ffmpeg*);;Todos (*)"
        )
        self.ffmpeg_path_selector.setPlaceholderText("Caminho para ffmpeg.exe")
        self.ffmpeg_path_selector.setReadOnly(True)
        self.ffmpeg_path_selector.button.clicked.connect(self.select_ffmpeg_signal.emit)
        
        config_layout.addWidget(self.ffmpeg_path_selector)
        self.layout.addWidget(config_group)

    def _setup_files_group(self):
        files_group = QGroupBox("Seleção de Arquivos")
        files_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        files_form_layout = QFormLayout(files_group)
        files_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        files_form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        files_form_layout.setSpacing(10)
        
        self.input_file_selector = PathSelector(
            selector_type=PathSelector.SELECT_FILE,
            dialog_title="Selecionar Vídeo de Entrada",
            file_filter="Vídeos (*.mp4 *.avi *.mov *.mkv *.webm *.flv);;Todos (*.*)"
        )
        self.input_file_selector.setPlaceholderText("Selecione o vídeo original")
        self.input_file_selector.button.clicked.connect(self.select_input_signal.emit)
        files_form_layout.addRow("Arquivo de Entrada:", self.input_file_selector)
        
        self.output_file_selector = PathSelector(
            selector_type=PathSelector.SAVE_FILE,
            dialog_title="Salvar Vídeo Comprimido Como",
            file_filter="Vídeo MP4 (*.mp4)"
        )
        self.output_file_selector.setPlaceholderText("Onde salvar o vídeo comprimido")
        self.output_file_selector.button.clicked.connect(self.select_output_signal.emit)
        files_form_layout.addRow("Arquivo de Saída:", self.output_file_selector)
        
        self.layout.addWidget(files_group)

    def _setup_preview_group(self):
        preview_group = QGroupBox("Pré-visualização")
        preview_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        preview_layout = QVBoxLayout(preview_group)
        
        self.video_preview = VideoPreview()
        preview_layout.addWidget(self.video_preview)
        
        self.input_file_selector.path_selected.connect(self.video_preview.set_video)
        
        self.layout.addWidget(preview_group)

    def _setup_quality_buttons_group(self):
        quality_group = QGroupBox("Qualidade da Compressão")
        quality_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        quality_layout = QHBoxLayout(quality_group)
        quality_layout.setSpacing(10)
        
        self.quality_button_group = QButtonGroup(self)
        self.quality_button_group.setExclusive(True)

        quality_button_style = """
            QPushButton {
                padding: 8px 15px;
                border: 1px solid #cccccc;
                background-color: #f0f0f0;
                color: #333333;
                font-weight: normal;
            }
            QPushButton:checked {
                background-color: #5c9eed;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:checked:hover {
                background-color: #4d8fd6;
            }
        """

        self.quality_agg_button = QPushButton("Agressiva")
        self.quality_agg_button.setCheckable(True)
        self.quality_agg_button.setStyleSheet(quality_button_style)
        self.quality_agg_button.setToolTip("Foco em reduzir tamanho, pode perder qualidade.")
        quality_layout.addWidget(self.quality_agg_button)
        self.quality_button_group.addButton(self.quality_agg_button)

        self.quality_med_button = QPushButton("Média")
        self.quality_med_button.setCheckable(True)
        self.quality_med_button.setStyleSheet(quality_button_style)
        self.quality_med_button.setToolTip("Bom equilíbrio entre tamanho e qualidade.")
        quality_layout.addWidget(self.quality_med_button)
        self.quality_button_group.addButton(self.quality_med_button)

        self.quality_high_button = QPushButton("Alta")
        self.quality_high_button.setCheckable(True)
        self.quality_high_button.setStyleSheet(quality_button_style)
        self.quality_high_button.setToolTip("Prioriza qualidade visual, arquivos maiores.")
        quality_layout.addWidget(self.quality_high_button)
        self.quality_button_group.addButton(self.quality_high_button)

        self.quality_agg_button.setChecked(True)
        
        # Codec selection
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["H.264 (AVC)", "H.265 (HEVC)", "VP9"])
        quality_layout.addWidget(self.codec_combo)
        
        # Resolution selection
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems([
            "Original", 
            "1080p (Full HD)", 
            "720p (HD)", 
            "480p (SD)", 
            "Personalizado..."
        ])
        quality_layout.addWidget(self.resolution_combo)
        
        # Advanced options toggle
        self.advanced_toggle = QPushButton("Opções Avançadas ▼")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.toggled.connect(self._toggle_advanced_options)
        quality_layout.addWidget(self.advanced_toggle)
        
        # Advanced panel
        self.advanced_panel = QWidget()
        advanced_layout = QFormLayout(self.advanced_panel)
        advanced_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # CRF Slider (Fixed: Using Qt.Orientation.Horizontal)
        self.crf_slider = QSlider(Qt.Orientation.Horizontal, self.advanced_panel)
        self.crf_slider.setRange(18, 32)
        self.crf_slider.setValue(23)
        advanced_layout.addRow("CRF:", self.crf_slider)
        
        # Custom resolution inputs
        self.custom_res_w = QLineEdit()
        self.custom_res_h = QLineEdit()
        self.custom_res_w.setPlaceholderText("Largura")
        self.custom_res_h.setPlaceholderText("Altura")
        
        res_layout = QHBoxLayout()
        res_layout.addWidget(self.custom_res_w)
        res_layout.addWidget(QLabel("x"))
        res_layout.addWidget(self.custom_res_h)
        
        advanced_layout.addRow("Resolução Personalizada:", res_layout)
        
        self.layout.addWidget(quality_group)
        self.layout.addWidget(self.advanced_panel)
        self.advanced_panel.hide()

    def _toggle_advanced_options(self, checked):
        self.advanced_panel.setVisible(checked)
        self.advanced_toggle.setText("Opções Avançadas ▲" if checked else "Opções Avançadas ▼")

    def get_selected_codec(self):
        return self.codec_combo.currentText()

    def get_selected_resolution(self):
        return self.resolution_combo.currentText()

    def get_custom_resolution(self):
        try:
            w = int(self.custom_res_w.text())
            h = int(self.custom_res_h.text())
            return (w, h)
        except:
            return None

    def get_crf_value(self):
        return self.crf_slider.value()

    def _setup_progress_group(self):
        progress_group = QGroupBox("Progresso e Controle")
        progress_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(10)
        
        self.size_chart = SizeComparisonChart()
        progress_layout.addWidget(self.size_chart)
        
        progress_bar_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                height: 20px;
            }
        """)
        
        self.eta_label = QLabel("ETA: --:--")
        self.eta_label.setObjectName("etaLabel")
        eta_font = self.eta_label.font()
        eta_font.setPointSize(eta_font.pointSize() + 1)
        eta_font.setBold(True)
        self.eta_label.setFont(eta_font)
        self.eta_label.setMinimumWidth(80)
        self.eta_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        progress_bar_layout.addWidget(self.progress_bar)
        progress_bar_layout.addWidget(self.eta_label)
        progress_layout.addLayout(progress_bar_layout)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.start_button = QPushButton("Iniciar Compressão")
        self.start_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
        self.start_button.clicked.connect(self._on_start_clicked)
        
        self.stop_button = QPushButton("Parar")
        self.stop_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop_compression_signal.emit)
        self.stop_button.setEnabled(False)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()
        progress_layout.addLayout(button_layout)
        self.layout.addWidget(progress_group)

    def _setup_log_group(self):
        log_group = QGroupBox("Log de Eventos")
        log_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(5, 15, 5, 5)
        
        self.log_area = LogWidget()
        self.log_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        log_container = QWidget()
        log_container.setLayout(QVBoxLayout())
        log_container.layout().addWidget(self.log_area)
        log_container.layout().setContentsMargins(0, 0, 0, 0)
        
        log_layout.addWidget(log_container)
        self.layout.addWidget(log_group, stretch=1)

    def _on_start_clicked(self):
        self.start_compression_signal.emit(
            self.ffmpeg_path_selector.get_path(),
            self.input_file_selector.get_path(),
            self.output_file_selector.get_path()
        )

    def get_ffmpeg_path(self): 
        return self.ffmpeg_path_selector.get_path()

    def get_input_path(self): 
        return self.input_file_selector.get_path()

    def get_output_path(self): 
        return self.output_file_selector.get_path()

    def set_ffmpeg_path(self, path): 
        self.ffmpeg_path_selector.set_path(path)

    def set_input_path(self, path): 
        self.input_file_selector.set_path(path)
        self.video_preview.set_video(path)

    def set_output_path(self, path): 
        self.output_file_selector.set_path(path)

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
        self.size_chart.update_sizes(0, 0)

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
        self.save_settings()
        self.closing.emit()
        event.ignore()
