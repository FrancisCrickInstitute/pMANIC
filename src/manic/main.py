import sys
from PySide6.QtWidgets import QApplication
from manic.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    manic = MainWindow()
    manic.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
