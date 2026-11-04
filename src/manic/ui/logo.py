import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel

from manic.ui import theme
from manic.utils.paths import resource_path


def logo_pixmap(height: int, device_pixel_ratio: float = 1.0) -> QPixmap:
    """The logo on a transparent background, its black lettering in the ``text`` token."""
    image = QImage(resource_path("resources", "manic_logo.png"))
    if image.isNull():
        return QPixmap()
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width, rows = image.width(), image.height()
    pixels = np.frombuffer(image.constBits(), np.uint8).reshape(rows, image.bytesPerLine())
    rgb = pixels[:, : width * 4].reshape(rows, width, 4)[..., :3] / 255.0

    # The artwork is ink on white: recover each pixel's ink colour and coverage.
    # The brand green (#22B573) lifts white by 0.867 at most, so dividing by
    # that keeps it solid instead of turning it translucent.
    alpha = np.clip((1.0 - rgb).max(axis=2) / 0.867, 0.0, 1.0)
    ink = 1.0 - (1.0 - rgb) / np.maximum(alpha, 1e-6)[..., None]
    neutral = ink.max(axis=2) - ink.min(axis=2) < 0.2
    text = theme.color("text")
    ink[neutral] = (text.redF(), text.greenF(), text.blueF())

    out = np.dstack([ink, alpha]).clip(0, 1)
    out = np.ascontiguousarray((out * 255).round().astype(np.uint8))
    result = QImage(out.data, width, rows, width * 4, QImage.Format.Format_RGBA8888).copy()
    pixmap = QPixmap.fromImage(result).scaledToHeight(
        round(height * device_pixel_ratio), Qt.TransformationMode.SmoothTransformation
    )
    pixmap.setDevicePixelRatio(device_pixel_ratio)
    return pixmap


class LogoLabel(QLabel):
    """The logo, redrawn when the colour scheme changes."""

    def __init__(self, height: int, parent=None):
        super().__init__(parent)
        self._height = height
        self._redraw()
        theme.notifier.changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, _remap: dict) -> None:
        self._redraw()

    def _redraw(self) -> None:
        self.setPixmap(logo_pixmap(self._height, self.devicePixelRatioF()))
