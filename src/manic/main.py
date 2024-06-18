import sys
from PySide6.QtWidgets import QApplication
from src.manic.gui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    manic = MainWindow()
    manic.showMaximized()
    sys.exit(app.exec())