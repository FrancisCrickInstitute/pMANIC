from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget


def show_over_parent(window: QWidget) -> None:
    """Show a secondary window centred on its parent, then bring it to the front.

    Without an explicit position macOS may place the window on whichever display
    is current, which drags focus to that display. Position only on first show
    so a window the user has moved stays where they put it.
    """
    parent = window.parentWidget()
    if parent is not None and parent.isVisible() and not window.property("placed"):
        frame = window.frameGeometry()
        frame.moveCenter(parent.frameGeometry().center())
        screen = QGuiApplication.screenAt(parent.frameGeometry().center())
        if screen is not None:
            area = screen.availableGeometry()
            frame.moveLeft(
                max(area.left(), min(frame.left(), area.right() - frame.width()))
            )
            frame.moveTop(
                max(area.top(), min(frame.top(), area.bottom() - frame.height()))
            )
        window.move(frame.topLeft())
        window.setProperty("placed", True)
    window.show()
    window.raise_()
    window.activateWindow()
