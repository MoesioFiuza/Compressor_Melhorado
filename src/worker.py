import os
import subprocess
import time
import re
from PySide6.QtCore import QObject, Signal
import traceback

class CompressionWorker(QObject):
    progress_updated = Signal(int, str)
    status_message = Signal(str, str)
    finished = Signal(int, str, float, float)
    error_occurred = Signal(str, str)

    INFO = "INFO"; WARN = "AVISO"; ERROR = "ERRO"; CMD = "CMD"; FFMPEG = "FFMPEG"

    def __init__(self, ffmpeg_path, input_file, output_file, 
                 quality_preset="Agressiva (Menor Arquivo)",
                 codec="H.264 (AVC)", resolution="Original",
                 custom_res=None, crf=None, parent=None):
        super().__init__(parent)
        self.ffmpeg_path = ffmpeg_path
        self.input_file = input_file
        self.output_file = output_file
        self.quality_preset = quality_preset
        self.codec = codec
        self.resolution = resolution
        self.custom_res = custom_res
        self.crf = crf
        self._is_running = True
        self.process = None

    def stop(self):
        self.status_message.emit("Tentativa de parada solicitada...", self.WARN)
        self._is_running = False
        if self.process and self.process.poll() is None:
            try:
                self.status_message.emit("Tentando parar o processo FFmpeg (terminate)...", self.WARN)
                self.process.terminate()
                try:
                    self.process.wait(timeout=1.0)
                    if self.process.poll() is not None:
                       self.status_message.emit("Processo FFmpeg parado via terminate.", self.WARN)
                       return
                except subprocess.TimeoutExpired:
                    pass

                if self.process.poll() is None:
                    self.status_message.emit("Processo FFmpeg não parou, forçando (kill)...", self.WARN)
                    self.process.kill()
                    self.process.wait()
                    self.status_message.emit("Processo FFmpeg forçado a parar.", self.WARN)
            except Exception as e:
                msg = f"Erro ao tentar parar FFmpeg: {e}"
                self.status_message.emit(msg, self.ERROR)
                self.error_occurred.emit("Erro ao Parar", msg)

    def run(self):
        start_time = time.time()
        original_file_size_mb = 0
        final_file_size_mb = 0
        return_code = 1

        try:
            if not self._is_running:
                self.status_message.emit("Execução cancelada antes de iniciar.", self.WARN)
                self.finished.emit(-1, self.output_file, 0, 0)
                return

            self.status_message.emit(f"Iniciando processamento: {os.path.basename(self.input_file)}", self.INFO)

            if not os.path.isfile(self.ffmpeg_path):
                msg = f"FFmpeg não encontrado em: {self.ffmpeg_path}"
                self.status_message.emit(msg, self.ERROR)
                self.error_occurred.emit("Erro Crítico de Configuração", msg)
                self.finished.emit(1, self.output_file, 0, 0)
                return
            
            if not os.path.isfile(self.input_file):
                msg = f"Arquivo de entrada não encontrado: {self.input_file}"
                self.status_message.emit(msg, self.ERROR)
                self.error_occurred.emit("Erro de Entrada", msg)
                self.finished.emit(1, self.output_file, 0, 0)
                return
            
            try:
                file_size_bytes = os.path.getsize(self.input_file)
                original_file_size_mb = file_size_bytes / (1024 * 1024)
                self.status_message.emit(f"Tamanho original: {original_file_size_mb:.2f} MB", self.INFO)
            except Exception as e:
                msg = f"Não foi possível obter o tamanho do arquivo de entrada: {e}"
                self.status_message.emit(msg, self.WARN)

            duration_seconds, width, height, fps = self._get_video_info()
            if duration_seconds is None:
                 self.finished.emit(1, self.output_file, original_file_size_mb, 0)
                 return

            # Configurações baseadas no codec selecionado
            codec_map = {
                "H.264 (AVC)": "libx264",
                "H.265 (HEVC)": "libx265",
                "VP9": "libvpx-vp9"
            }
            target_codec = codec_map.get(self.codec, "libx264")

            # Configurações de qualidade
            if self.crf is not None:
                target_crf = str(self.crf)
            else:
                target_crf = {
                    "Alta (Melhor Qualidade)": "20",
                    "Média (Balanceado)": "24",
                    "Agressiva (Menor Arquivo)": "28"
                }.get(self.quality_preset, "23")

            target_preset = {
                "Alta (Melhor Qualidade)": "medium",
                "Média (Balanceado)": "fast",
                "Agressiva (Menor Arquivo)": "veryfast"
            }.get(self.quality_preset, "fast")

            skip_frames = {
                "Alta (Melhor Qualidade)": 0,
                "Média (Balanceado)": 1,
                "Agressiva (Menor Arquivo)": 2
            }.get(self.quality_preset, 1)

            target_audio_bitrate = {
                "Alta (Melhor Qualidade)": "160k",
                "Média (Balanceado)": "128k",
                "Agressiva (Menor Arquivo)": "96k"
            }.get(self.quality_preset, "128k")

            output_fps = max(1.0, fps / (skip_frames + 1))

            # Configuração de resolução
            scale_filter = ""
            if self.resolution != "Original":
                if self.resolution == "Personalizado..." and self.custom_res:
                    scale_filter = f"scale={self.custom_res[0]}:{self.custom_res[1]}:flags=lanczos"
                else:
                    resolutions = {
                        "1080p (Full HD)": "scale=-2:1080",
                        "720p (HD)": "scale=-2:720",
                        "480p (SD)": "scale=-2:480"
                    }
                    scale_filter = resolutions.get(self.resolution, "")

            # Montar comando FFmpeg
            compress_command = [
                self.ffmpeg_path, '-y',
                '-i', self.input_file,
                '-c:v', target_codec,
                '-crf', target_crf,
                '-preset', target_preset,
                '-movflags', '+faststart'
            ]

            # Adicionar filtros
            if scale_filter:
                compress_command.extend(['-vf', f"{scale_filter},fps={output_fps}"])
            else:
                compress_command.extend(['-vf', f"fps={output_fps}"])

            # Configurações específicas por codec
            if target_codec == "libx265":
                compress_command.extend(['-x265-params', 'log-level=error'])
            elif target_codec == "libvpx-vp9":
                compress_command.extend(['-quality', 'good', '-cpu-used', '4'])

            # Adicionar áudio e saída
            compress_command.extend([
                '-c:a', 'aac',
                '-b:a', target_audio_bitrate,
                self.output_file
            ])

            self.status_message.emit(f"Configurações: Codec={target_codec}, CRF={target_crf}, Preset={target_preset}", self.INFO)
            self.status_message.emit(f"Resolução: {self.resolution}, FPS Saída: {output_fps:.1f}", self.INFO)
            self.status_message.emit("Iniciando compressão FFmpeg...", self.INFO)

            cmd_str = ' '.join(f'"{c}"' if ' ' in c else c for c in compress_command)
            self.status_message.emit(f"Comando: {cmd_str}", self.CMD)

            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NO_WINDOW

            try:
                self.process = subprocess.Popen(
                    compress_command,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True, encoding='utf-8', errors='replace', bufsize=1,
                    startupinfo=startupinfo, creationflags=creationflags
                )
            except FileNotFoundError:
                msg = f"Erro Crítico: FFmpeg não pôde ser executado:\n{self.ffmpeg_path}"
                self.status_message.emit(msg, self.ERROR)
                self.error_occurred.emit("Erro ao Executar FFmpeg", msg)
                self.finished.emit(1, self.output_file, original_file_size_mb, 0)
                return
            except Exception as e:
                 msg = f"Erro Crítico ao iniciar processo FFmpeg: {e}"
                 self.status_message.emit(msg, self.ERROR)
                 self.error_occurred.emit("Erro Crítico FFmpeg", msg)
                 self.finished.emit(1, self.output_file, original_file_size_mb, 0)
                 return

            progress_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
            last_progress_update_time = 0
            duration_for_progress = duration_seconds if duration_seconds > 0 else 1

            if self.process.stderr:
                for line in iter(self.process.stderr.readline, ''):
                    if not self._is_running:
                        self.status_message.emit("Parada detectada durante processamento.", self.WARN)
                        break
                    if "error" in line.lower() or "invalid" in line.lower():
                         self.status_message.emit(f"[FFmpeg]: {line.strip()}", self.WARN)
                    match = progress_pattern.search(line)
                    if match and duration_for_progress > 1:
                        h, m, s = match.groups()
                        current_seconds = int(h) * 3600 + int(m) * 60 + float(s)
                        percent = min(100, int(100 * current_seconds / duration_for_progress))
                        elapsed_time = time.time() - start_time
                        eta_seconds = float('inf')
                        if current_seconds > 0 and elapsed_time > 1:
                            speed = current_seconds / elapsed_time
                            remaining_seconds_video = duration_for_progress - current_seconds
                            if speed > 0: eta_seconds = remaining_seconds_video / speed
                        current_time = time.time()
                        if current_time - last_progress_update_time >= 0.5:
                            eta_str = f"ETA: {time.strftime('%M:%S', time.gmtime(eta_seconds))}" if eta_seconds != float('inf') else "ETA: ..."
                            self.progress_updated.emit(percent, eta_str)
                            last_progress_update_time = current_time
                self.process.stderr.close()

            self.process.wait()
            return_code = self.process.returncode
            stdout_data = self.process.stdout.read() if self.process.stdout else ""
            self.process.stdout.close() if self.process.stdout else None

            if not self._is_running and return_code != 0:
                 self.status_message.emit("Compressão cancelada pelo usuário.", self.WARN)
                 self.finished.emit(-1, self.output_file, original_file_size_mb, 0)
                 return

            if return_code == 0 and duration_for_progress > 1:
                 self.progress_updated.emit(100, "ETA: 00:00")

            if return_code == 0:
                 try:
                     if os.path.exists(self.output_file) and os.path.getsize(self.output_file) > 0:
                         final_file_size_mb = os.path.getsize(self.output_file) / (1024 * 1024)
                         self.status_message.emit(f"✓ Compressão concluída: {os.path.basename(self.output_file)}", self.INFO)
                         self.status_message.emit(f"Tamanho final: {final_file_size_mb:.2f} MB", self.INFO)
                         if original_file_size_mb > 0:
                             reduction = 100 - (final_file_size_mb / original_file_size_mb * 100)
                             self.status_message.emit(f"Redução de: {reduction:.1f}%", self.INFO)
                         total_time = time.time() - start_time
                         self.status_message.emit(f"Tempo total: {time.strftime('%H:%M:%S', time.gmtime(total_time))}", self.INFO)
                     else:
                         msg = f"✗ Erro Pós-Compressão: Arquivo de saída '{os.path.basename(self.output_file)}' não encontrado ou vazio, apesar do FFmpeg retornar 0."
                         self.status_message.emit(msg, self.ERROR)
                         self.error_occurred.emit("Erro Pós-Compressão", msg)
                         return_code = 1
                 except Exception as e:
                     msg = f"✗ Erro ao verificar arquivo de saída: {str(e)}"
                     self.status_message.emit(msg, self.ERROR)
                     self.error_occurred.emit("Erro Pós-Compressão", msg)
                     return_code = 1
            else:
                 msg = f"✗ Erro na compressão com FFmpeg (Código: {return_code})."
                 self.status_message.emit(msg, self.ERROR)
                 if stdout_data:
                     self.status_message.emit(f"--- Saída Padrão FFmpeg (stdout) ---", self.FFMPEG)
                     self.status_message.emit(stdout_data, self.FFMPEG)
                     self.status_message.emit(f"------------------------------------", self.FFMPEG)
                 self.error_occurred.emit("Erro FFmpeg", f"FFmpeg falhou (código {return_code}). Verifique os logs na janela principal.")

        except Exception as e:
            msg = f"Erro inesperado no worker: {e.__class__.__name__}: {e}"
            try:
                msg += f"\nTraceback:\n{traceback.format_exc()}"
            except ImportError: pass
            self.status_message.emit(msg, self.ERROR)
            self.error_occurred.emit("Erro Interno do Worker", msg)
            return_code = 1
        finally:
            if not self._is_running and return_code == 0:
                 self.finished.emit(-1, self.output_file, original_file_size_mb, final_file_size_mb)
            else:
                 self.finished.emit(return_code, self.output_file, original_file_size_mb, final_file_size_mb)

    def _get_video_info(self):
        self.status_message.emit("Obtendo informações do vídeo...", self.INFO)
        info_command = [self.ffmpeg_path, '-i', self.input_file, '-hide_banner']
        startupinfo = None
        creationflags = 0
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW
        try:
            result = subprocess.run(info_command, capture_output=True, text=True,
                                     encoding='utf-8', errors='replace', check=False,
                                     startupinfo=startupinfo, creationflags=creationflags,
                                     timeout=15)
            info_output = result.stderr
            if not info_output: info_output = result.stdout
            duration_match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', info_output)
            resolution_match = re.search(r'Stream.*Video:.*?,.*? (\d{2,5})x(\d{2,5})', info_output)
            fps_match = re.search(r'Stream.*Video:.*?,.*?(\d+(?:\.\d+)?) (?:fps|tbr)', info_output)
            duration_seconds = 0
            if duration_match:
                h, m, s = duration_match.groups()
                duration_seconds = int(h) * 3600 + int(m) * 60 + float(s)
                self.status_message.emit(f"Duração detectada: {time.strftime('%H:%M:%S', time.gmtime(duration_seconds))}", self.INFO)
            else:
                duration_match_alt = re.search(r'Duration: N/A, start: \d+\.\d+, bitrate:.*?Duration: (\d+\.\d+)', info_output, re.IGNORECASE | re.DOTALL)
                if duration_match_alt:
                     duration_seconds = float(duration_match_alt.group(1))
                     self.status_message.emit(f"Duração detectada (alt): {time.strftime('%H:%M:%S', time.gmtime(duration_seconds))}", self.INFO)
                else:
                     self.status_message.emit("Aviso: Não foi possível detectar a duração do vídeo. Progresso será impreciso.", self.WARN)
            width, height = 1920, 1080
            if resolution_match:
                width, height = int(resolution_match.group(1)), int(resolution_match.group(2))
            else:
                self.status_message.emit("Aviso: Não foi possível detectar a resolução. Usando fallback 1920x1080.", self.WARN)
            fps = 30.0
            if fps_match:
                try: fps = float(fps_match.group(1))
                except ValueError: self.status_message.emit(f"Aviso: Valor de FPS inválido ('{fps_match.group(1)}'). Usando fallback {fps:.1f} fps.", self.WARN)
            else: self.status_message.emit(f"Aviso: Não foi possível detectar o FPS. Usando fallback {fps:.1f} fps.", self.WARN)
            return duration_seconds, width, height, fps
        except subprocess.TimeoutExpired:
             msg = "Erro: FFmpeg demorou demais para responder ao obter informações do vídeo."
             self.status_message.emit(msg, self.ERROR)
             self.error_occurred.emit("Erro FFmpeg", msg)
             return None, None, None, None
        except FileNotFoundError:
             msg = f"Erro Crítico: FFmpeg não pôde ser executado para obter info:\n{self.ffmpeg_path}"
             self.status_message.emit(msg, self.ERROR)
             self.error_occurred.emit("Erro ao Executar FFmpeg", msg)
             return None, None, None, None
        except Exception as e:
             msg = f"Erro inesperado ao obter informações do vídeo: {e.__class__.__name__}: {e}"
             self.status_message.emit(msg, self.ERROR)
             self.error_occurred.emit("Erro de Análise", msg)
             return None, None, None, None
