from PySide6.QtCore import QEvent, QObject, QPoint
from PySide6.QtWidgets import QWidget

from manic.ui.standard_chooser import StandardChooser


# Sidebar heights in a 1024x640, 1280x720 and 1024x768 window (menu and status bar taken off).
LAPTOP_640 = 587
LAPTOP_720 = 667
LAPTOP_768 = 715


# 680 is about the sidebar of a 1024x768 window with a taller menu bar.


def test_building_the_standard_chooser_opens_no_other_window(qapp):
    # On Windows a stray window takes activation, and Qt then closes the popup at once.
    shown = []

    class Spy(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Show and isinstance(obj, QWidget) and obj.isWindow():
                shown.append(type(obj).__name__)
            return False

    spy = Spy()
    qapp.installEventFilter(spy)
    parent = QWidget()
    try:
        chooser = StandardChooser(["Alanine", "Glycine"], None, set(), parent)
        chooser.popup(QPoint(10, 10))
        qapp.processEvents()
        assert shown == ["StandardChooser"]
        chooser.close()
    finally:
        qapp.removeEventFilter(spy)
        parent.deleteLater()
