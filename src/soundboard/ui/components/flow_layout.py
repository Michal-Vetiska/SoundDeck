"""Wrapping grid whose column count follows the window width."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget


def columns_for_width(width: int) -> int:
    """Narrow windows show 2 columns, medium 3, wide windows 4 or more."""
    if width < 780:
        return 2
    if width < 1100:
        return 3
    return max(4, width // 280)


class FlowLayout(QLayout):
    """Place items in a wrapping grid with equal column widths."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._horizontal_gap = 16
        self._vertical_gap = 16
        self._row_height = 196
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        inner = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        if inner.width() <= 0:
            return margins.top() + margins.bottom()
        columns = columns_for_width(inner.width()) if self._items else 1
        column_width = (inner.width() - (columns - 1) * self._horizontal_gap) / columns
        for index, item in enumerate(self._items):
            column = index % columns
            row = index // columns
            x = inner.x() + column * (column_width + self._horizontal_gap)
            y = inner.y() + row * (self._row_height + self._vertical_gap)
            if not test_only:
                item.setGeometry(QRect(int(x), int(y), int(column_width), self._row_height))
        rows = (len(self._items) + columns - 1) // max(columns, 1) if self._items else 0
        total = rows * self._row_height + max(0, rows - 1) * self._vertical_gap
        return total + margins.top() + margins.bottom()
