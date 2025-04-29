import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from view import CompressorView
from controller import CompressionController

if __name__ == '__main__':

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    try:
        main_window = CompressorView()
    except Exception as e:
        print(f"ERRO CRÍTICO: Falha ao criar a instância da View (CompressorView): {e}")
        QMessageBox.critical(None, "Erro Crítico na UI", f"Não foi possível iniciar a interface gráfica:\n{e}")
        sys.exit(1)

    try:
        controller = CompressionController(view=main_window)
    except Exception as e:
        print(f"ERRO CRÍTICO: Falha ao criar a instância do Controller: {e}")
        QMessageBox.critical(None, "Erro Crítico no Controller", f"Não foi possível iniciar o controlador da aplicação:\n{e}")
        sys.exit(1)

    try:
        main_window.show()
    except Exception as e:
        print(f"ERRO CRÍTICO: Falha ao exibir a janela principal: {e}")
        sys.exit(1)

    exit_code = app.exec()
    sys.exit(exit_code)