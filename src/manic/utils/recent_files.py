import os

from PySide6.QtCore import QSettings


class RecentFiles:
    def __init__(
        self,
        kind: str,
        limit: int = 8,
        settings: QSettings | None = None,
    ):
        self._kind = kind
        self._limit = limit
        self._settings = settings if settings is not None else QSettings()
        self._key = f"recent/{kind}"

    def add(self, path: str) -> None:
        normalized = os.path.abspath(path)
        current = [item for item in self._stored() if item != normalized]
        current.insert(0, normalized)
        self._write(current[: self._limit])

    def paths(self) -> list[str]:
        return [path for path in self._stored() if os.path.exists(path)]

    def clear(self) -> None:
        self._settings.remove(self._key)

    def _stored(self) -> list[str]:
        value = self._settings.value(self._key)
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        return [str(item) for item in value if item]

    def _write(self, paths: list[str]) -> None:
        self._settings.setValue(self._key, paths)
