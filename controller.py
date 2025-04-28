from PySide6 import QtCore
import os
import sys
import time
import subprocess
from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from view import CompressorView, PathSelector
from worker import CompressionWorker
from config import load_ffmpeg_path, save_ffmpeg_path, get_base_path

class CompressionController(QObject):

    def __init__(self, view: CompressorView, parent=None):
        super().__init__(parent)
        self.view = view
        self.compression_thread = None
        self.compression_worker = None
        self.ffmpeg_path = None
        self.input_file = None
        self.output_file = None
        self._connect_signals()
        self._load_initial_ffmpeg_path()
        self.view.set_ui_busy(False)

    def _connect_signals(self):
        self.view.select_ffmpeg_signal.connect(self.select_ffmpeg_executable)
        self.view.select_input_signal.connect(self.select_input_video)
        self.view.select_output_signal.connect(self.select_output_location)
        self.view.start_compression_signal.connect(self.start_compression)
        self.view.stop_compression_signal.connect(self.stop_compression)
        self.view.closing.connect(self.handle_window_close)

    def _load_initial_ffmpeg_path(self):
        loaded_path = load_ffmpeg_path()
        if not loaded_path:
            base = get_base_path()
            potential_paths = []
            if getattr(sys, 'frozen', False):
                potential_paths.append(os.path.join(base, "_internal", "ffmpeg.exe"))
                potential_paths.append(os.path.join(base, "ffmpeg.exe"))
            else:
                potential_paths.append(os.path.join(base, "ffmpeg.exe"))

            for path in potential_paths:
                if os.path.isfile(path):
                    loaded_path = path
                    self.view.log_message(f"FFmpeg encontrado automaticamente: {loaded_path}", "INFO")
                    save_ffmpeg_path(loaded_path)
                    break

        if loaded_path and os.path.isfile(loaded_path):
            self.ffmpeg_path = loaded_path
            self.view.set_ffmpeg_path(self.ffmpeg_path)
            self.view.log_message(f"Usando FFmpeg de: {self.ffmpeg_path}", "INFO")
        else:
            self.ffmpeg_path = None
            self.view.log_message("FFmpeg não configurado. Selecione o executável.", "WARN")

    @Slot()
    def select_ffmpeg_executable(self):
        self.view.log_message("Abrindo diálogo para selecionar FFmpeg...", "INFO")
        initial_dir = os.path.dirname(self.ffmpeg_path) if self.ffmpeg_path else get_base_path()
        filter_str = "Executável FFmpeg (ffmpeg.exe)" if os.name == 'nt' else "Executável FFmpeg (ffmpeg)"
        filter_str += ";;Todos os Arquivos (*)"

        selected_path, _ = QFileDialog.getOpenFileName(
            self.view,
            "Selecione o executável do FFmpeg",
            initial_dir,
            filter_str
        )
        is_valid_ffmpeg = (selected_path and os.path.isfile(selected_path) and
                           'ffmpeg' in os.path.basename(selected_path).lower())

        if is_valid_ffmpeg:
            self.ffmpeg_path = selected_path
            self.view.set_ffmpeg_path(self.ffmpeg_path)
            save_ffmpeg_path(self.ffmpeg_path)
            self.view.log_message(f"FFmpeg definido para: {self.ffmpeg_path}", "INFO")
        elif selected_path:
             self.view.show_error_message("Seleção Inválida", f"Arquivo selecionado não parece ser um executável FFmpeg válido:\n{selected_path}")
        else:
            self.view.log_message("Seleção de FFmpeg cancelada.", "INFO")

        self.view.set_ui_busy(False)

    @Slot()
    def select_input_video(self):
        self.view.log_message("Abrindo diálogo para selecionar vídeo de entrada...", "INFO")
        current_input = self.view.get_input_path()
        initial_dir = os.path.dirname(current_input) if current_input else os.path.expanduser("~")
        filter_str = "Arquivos de vídeo (*.mp4 *.avi *.mov *.mkv *.webm *.flv);;Todos os Arquivos (*.*)"

        selected_path, _ = QFileDialog.getOpenFileName(
            self.view,
            "Selecione o arquivo de vídeo para compressão",
            initial_dir,
            filter_str
        )
        if selected_path and os.path.isfile(selected_path):
            self.input_file = selected_path
            self.view.set_input_path(self.input_file)
            self.view.log_message(f"Arquivo de entrada selecionado: {self.input_file}", "INFO")
            self._suggest_output_filename()
        elif selected_path:
             self.view.show_error_message("Seleção Inválida", f"Caminho selecionado não é um arquivo válido:\n{selected_path}")
        else:
            self.view.log_message("Seleção de vídeo de entrada cancelada.", "INFO")

        self.view.set_ui_busy(False)

    def _suggest_output_filename(self):
        if not self.input_file: return

        input_dir = os.path.dirname(self.input_file)
        base_name = os.path.splitext(os.path.basename(self.input_file))[0]
        default_output_name = f"{base_name}_comprimido.mp4"
        suggested_path = os.path.join(input_dir, default_output_name)
        count = 1
        final_path = suggested_path

        while os.path.exists(final_path):
            final_path = os.path.join(input_dir, f"{base_name}_comprimido_{count}.mp4")
            count += 1

        self.output_file = final_path
        self.view.set_output_path(final_path)
        self.view.log_message(f"Nome de arquivo de saída sugerido: {os.path.basename(final_path)}", "INFO")

    @Slot()
    def select_output_location(self):
        self.view.log_message("Abrindo diálogo para definir local de saída...", "INFO")
        current_output = self.view.get_output_path()
        initial_dir = os.path.dirname(current_output) if current_output else \
                      os.path.dirname(self.input_file) if self.input_file else \
                      os.path.expanduser("~")
        default_name = os.path.basename(current_output) if current_output else "video_comprimido.mp4"
        filter_str = "Arquivos MP4 (*.mp4)"

        selected_path, _ = QFileDialog.getSaveFileName(
            self.view,
            "Selecione onde salvar o arquivo comprimido",
            os.path.join(initial_dir, default_name),
            filter_str
        )
        if selected_path:
            if not selected_path.lower().endswith('.mp4'):
                selected_path += '.mp4'
            self.output_file = selected_path
            self.view.set_output_path(self.output_file)
            self.view.log_message(f"Arquivo de saída definido como: {self.output_file}", "INFO")
        else:
            self.view.log_message("Seleção de local de saída cancelada.", "INFO")

        self.view.set_ui_busy(False)

    @Slot(str, str, str)
    def start_compression(self, ffmpeg_path_view, input_file_view, output_file_view):
        self.view.log_message("Botão 'Iniciar Compressão' clicado.", "INFO")

        self.ffmpeg_path = ffmpeg_path_view
        self.input_file = input_file_view
        self.output_file = output_file_view

        if not self.ffmpeg_path or not os.path.isfile(self.ffmpeg_path):
            self.view.show_error_message("Erro de Configuração", "Caminho para o FFmpeg inválido ou não definido.")
            return
        if not self.input_file or not os.path.isfile(self.input_file):
            self.view.show_error_message("Erro de Entrada", "Arquivo de vídeo de entrada inválido ou não selecionado.")
            return
        if not self.output_file:
            self.view.show_error_message("Erro de Saída", "Local para salvar o arquivo de saída não selecionado.")
            return
        try:
             if os.path.abspath(self.input_file) == os.path.abspath(self.output_file):
                  self.view.show_error_message("Erro de Saída", "O arquivo de saída não pode ser o mesmo que o arquivo de entrada.")
                  return
        except Exception as e:
             self.view.show_error_message("Erro de Path", f"Erro ao comparar caminhos de entrada e saída: {e}")
             return

        output_dir = os.path.dirname(self.output_file)
        if not os.path.isdir(output_dir):
              try:
                  os.makedirs(output_dir, exist_ok=True)
                  self.view.log_message(f"Diretório de saída criado: {output_dir}", "INFO")
              except Exception as e:
                  self.view.show_error_message("Erro de Saída", f"Não foi possível criar o diretório de saída:\n{output_dir}\n{e}")
                  return

        selected_quality = self.view.get_selected_quality()
        self.view.log_message(f"Perfil de qualidade selecionado: {selected_quality}", "INFO")

        self.view.clear_log()
        self.view.reset_progress()
        self.view.set_ui_busy(True)

        self.compression_thread = QThread(self)
        self.compression_worker = CompressionWorker(
            self.ffmpeg_path,
            self.input_file,
            self.output_file,
            quality_preset=selected_quality
        )
        self.compression_worker.moveToThread(self.compression_thread)

        self.compression_worker.progress_updated.connect(self._handle_progress)
        self.compression_worker.status_message.connect(self._handle_status)
        self.compression_worker.finished.connect(self._handle_finished)
        self.compression_worker.error_occurred.connect(self._handle_error)

        self.compression_thread.started.connect(self.compression_worker.run)
        self.compression_worker.finished.connect(self.compression_thread.quit)
        self.compression_worker.finished.connect(self.compression_worker.deleteLater)
        self.compression_thread.finished.connect(self.compression_thread.deleteLater)
        self.compression_thread.finished.connect(self._cleanup_references)

        self.view.log_message("Iniciando thread de compressão...", "INFO")
        self.compression_thread.start()

    @Slot()
    def stop_compression(self):
        if self.compression_worker and self.compression_thread and self.compression_thread.isRunning():
              self.view.log_message("Sinal de parada enviado para o worker...", "WARN")
              self.compression_worker.stop()
              self.view.stop_button.setEnabled(False)
        else:
              self.view.log_message("Nenhuma compressão ativa para parar.", "INFO")

    @Slot(int, str)
    def _handle_progress(self, percent, eta_str):
        self.view.update_progress(percent, eta_str)

    @Slot(str, str)
    def _handle_status(self, message, level):
        self.view.log_message(message, level)

    @Slot(str, str)
    def _handle_error(self, title, message):
        self.view.show_error_message(title, message)

    @Slot(int, str, float, float)
    def _handle_finished(self, return_code, output_file, original_mb, final_mb):
        self.view.log_message(f"Thread de compressão finalizada com código: {return_code}", "INFO")
        self.view.set_ui_busy(False)
        self.view.reset_progress()

        if return_code == 0:
            reduction_str = ""
            if original_mb > 0 and final_mb > 0:
                reduction = 100 - (final_mb / original_mb * 100)
                reduction_str = f" ({reduction:.1f}% de redução)"

            final_msg = (f"Compressão finalizada com sucesso!\n"
                         f"Arquivo salvo em: {output_file}\n"
                         f"Tamanho final: {final_mb:.2f} MB{reduction_str}")
            self.view.log_message("-------------------------------------", "INFO")
            self.view.log_message(final_msg, "INFO")
            self.view.log_message("-------------------------------------", "INFO")

        elif return_code == -1:
             try:
                 self.view.show_warning_message("Cancelado", "A operação de compressão foi cancelada.")
             except AttributeError:
                 self.view.log_message("Operação cancelada pelo usuário.", "WARN")
                 QMessageBox.warning(self.view, "Cancelado", "A operação de compressão foi cancelada.")
             self.view.log_message("Operação cancelada pelo usuário.", "WARN")
        else:
             self.view.log_message(f"Compressão falhou. Verifique os logs acima.", "ERROR")

    @Slot()
    def _cleanup_references(self):
        self.compression_thread = None
        self.compression_worker = None
        self.view.log_message("Referências internas da thread limpas.", "INFO")

    def _ask_open_output_directory(self, output_file):
         try:
             output_dir = os.path.dirname(output_file)
             pass
         except Exception as e:
            self.view.log_message(f"Erro ao perguntar sobre abrir diretório: {e}", "WARN")

    def _open_output_directory(self, directory):
         if not os.path.isdir(directory):
              self.view.log_message(f"Diretório não encontrado: {directory}", "WARN")
              return
         try:
             if sys.platform == 'win32':
                 os.startfile(directory)
             elif sys.platform == 'darwin':
                 subprocess.Popen(['open', directory])
             else:
                 subprocess.Popen(['xdg-open', directory])
             self.view.log_message(f"Tentando abrir diretório: {directory}", "INFO")
         except Exception as e:
             self.view.log_message(f"Não foi possível abrir a pasta automaticamente: {e}", "ERROR")

    @Slot()
    def handle_window_close(self):
        if self.compression_thread and self.compression_thread.isRunning():
            if self.view.confirm_exit_dialog():
                self.view.log_message("Parando compressão para fechar a janela...", "WARN")
                self.stop_compression()
                if self.compression_worker:
                    self.compression_worker.finished.connect(self.view.close, Qt.ConnectionType.SingleShotConnection)
                else:
                     self.view.close()
            else:
                self.view.log_message("Fechamento da janela cancelado pelo usuário.", "INFO")
        else:
            self.view.close()