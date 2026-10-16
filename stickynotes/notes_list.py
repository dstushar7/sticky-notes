# stickynotes/notes_list.py
"""
Notes List Window for Sticky Notes.

Replicates the Microsoft Sticky Notes 'Notes list' hub:
- Header bar with '+' (new note), '⚙' (settings), and '✕' (close).
- Bold 'Sticky Notes' title.
- Real-time search filter with magnifying glass icon.
- Scrollable list of cards displaying note preview, custom top-border accent
  matching the note's theme color, and last edited date (e.g. 'Oct 2').
- Click or double-click to open/raise note.
- Context menu for quick opening or deleting.
- Synchronizes with SQLite database and active note windows.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, QSettings, QByteArray, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QIcon,
    QMouseEvent,
    QKeySequence,
    QShortcut,
    QTextDocument,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QFrame,
    QSizeGrip,
    QMenu,
    QMessageBox,
    QGraphicsDropShadowEffect,
    QSizePolicy,
    QApplication,
)

from . import config, utils, storage
from .widgets import FloatingButton


def format_note_date(iso_str: Optional[str]) -> str:
    """Format an ISO-8601 timestamp into a sleek short date like 'Oct 2' or 'Today'."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        now = datetime.now()
        if dt.date() == now.date():
            return "Today"
        # Format month and day (strip leading zero on day)
        day = str(dt.day)
        month = dt.strftime("%b")
        if dt.year == now.year:
            return f"{month} {day}"
        return f"{month} {day}, {dt.year}"
    except Exception:
        if len(iso_str) >= 10:
            return iso_str[:10]
        return ""


def get_plain_snippet(html_content: str, max_chars: int = 240) -> str:
    """Extract clean plain text from HTML, collapsing excess whitespace."""
    if not html_content:
        return ""
    doc = QTextDocument()
    doc.setHtml(html_content)
    plain = doc.toPlainText().strip()
    # Normalize multiple blank lines to double newlines
    lines = [line.strip() for line in plain.splitlines() if line.strip()]
    cleaned = "\n".join(lines)
    if len(cleaned) > max_chars:
        return cleaned[:max_chars].rstrip() + "…"
    return cleaned


class NoteCardWidget(QFrame):
    """Individual note preview card in the Notes List."""

    openRequested = pyqtSignal(str)
    deleteRequested = pyqtSignal(str)

    _THEME_ACCENTS = {
        "yellow":   "#E5C100",
        "green":    "#78C88B",
        "pink":     "#F48FAA",
        "purple":   "#B680F2",
        "blue":     "#5DC3F3",
        "gray":     "#A8A8A8",
        "charcoal": "#888888",
    }

    def __init__(self, note_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.note_data = note_data
        self.note_id = note_data["id"]
        self.is_open = bool(note_data.get("is_open", False))
        self.setObjectName("noteCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._hovered = False

        self._theme_name = note_data.get("theme", config.DEFAULT_THEME)
        self._accent_color = self._THEME_ACCENTS.get(self._theme_name, "#E5C100")

        self._setup_ui()
        self._apply_style()

    def set_open(self, is_open: bool):
        """Update open status and repaint dog-ear folded corner indicator."""
        if self.is_open != is_open:
            self.is_open = is_open
            self.note_data["is_open"] = is_open
            self.update()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 15, 14, 13)
        layout.setSpacing(6)

        # Top row: Title (if available) + Date on right
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        title_text = self.note_data.get("title") or ""
        self.title_label = QLabel(title_text)
        self.title_label.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 11pt; background: transparent;")
        self.title_label.setVisible(bool(title_text and title_text != config.DEFAULT_NOTE_TITLE))

        date_text = format_note_date(self.note_data.get("last_edited"))
        self.date_label = QLabel(date_text)
        # Timestamp color matches the specific note's theme color
        self.date_label.setStyleSheet(f"color: {self._accent_color}; font-size: 9pt; font-weight: 500; background: transparent;")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        top_row.addWidget(self.title_label, stretch=1)
        top_row.addWidget(self.date_label, stretch=0)
        layout.addLayout(top_row)

        # Body snippet preview
        body_text = get_plain_snippet(self.note_data.get("content", ""))
        # If no body and no title, show placeholder
        if not body_text and not title_text:
            body_text = "Empty note"

        self.body_label = QLabel(body_text)
        self.body_label.setWordWrap(True)
        self.body_label.setStyleSheet("color: #d4d4d4; font-size: 10pt; line-height: 1.3; background: transparent;")
        layout.addWidget(self.body_label)

    def _apply_style(self):
        self.setStyleSheet("""
            QFrame#noteCard {
                background-color: transparent;
                border: none;
            }
        """)

    def paintEvent(self, event):
        """Paint rounded card with note color filling the top edge and inner corners,
        and a folded bottom-right corner if the note is currently open."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        radius = 6.0
        fold_size = 14.0 if self.is_open else 0.0
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        x1, y1 = rect.left(), rect.top()
        x2, y2 = rect.right(), rect.bottom()

        card_path = QPainterPath()
        card_path.moveTo(x1 + radius, y1)
        card_path.lineTo(x2 - radius, y1)
        card_path.arcTo(x2 - 2 * radius, y1, 2 * radius, 2 * radius, 90, -90)

        if self.is_open:
            card_path.lineTo(x2, y2 - fold_size)
            card_path.lineTo(x2 - fold_size, y2)
        else:
            card_path.lineTo(x2, y2 - radius)
            card_path.arcTo(x2 - 2 * radius, y2 - 2 * radius, 2 * radius, 2 * radius, 0, -90)

        card_path.lineTo(x1 + radius, y2)
        card_path.arcTo(x1, y2 - 2 * radius, 2 * radius, 2 * radius, 270, -90)
        card_path.lineTo(x1, y1 + radius)
        card_path.arcTo(x1, y1, 2 * radius, 2 * radius, 180, -90)
        card_path.closeSubpath()

        # 1. Base card background
        bg_color = QColor("#363636" if self._hovered else "#2b2b2b")
        p.fillPath(card_path, bg_color)

        # 2. Solid top accent stripe (fills top edge, hugging and rounding the inner corners)
        stripe_height = 5.0
        p.save()
        p.setClipPath(card_path)
        stripe_rect = QRectF(rect.x(), rect.y(), rect.width(), stripe_height)
        p.fillRect(stripe_rect, QColor(self._accent_color))
        p.restore()

        # 3. Outer border
        border_color = QColor("#4a4a4a" if self._hovered else "#383838")
        p.setPen(QPen(border_color, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(card_path)

        # 4. Dog-ear folded corner flap if open
        if self.is_open:
            flap_path = QPainterPath()
            flap_path.moveTo(x2 - fold_size, y2)
            flap_path.lineTo(x2 - fold_size, y2 - fold_size)
            flap_path.lineTo(x2, y2 - fold_size)
            flap_path.closeSubpath()

            # Paper back color (lighter grey)
            flap_color = QColor("#5c5c5c" if self._hovered else "#525252")
            p.fillPath(flap_path, flap_color)

            # Crease line (darker diagonal fold)
            p.setPen(QPen(QColor("#2d2d2d"), 1))
            p.drawLine(QPointF(x2 - fold_size, y2), QPointF(x2, y2 - fold_size))

            # Subtle inner paper edge highlights
            p.setPen(QPen(QColor("#686868" if self._hovered else "#5e5e5e"), 1))
            p.drawLine(QPointF(x2 - fold_size, y2), QPointF(x2 - fold_size, y2 - fold_size))
            p.drawLine(QPointF(x2 - fold_size, y2 - fold_size), QPointF(x2, y2 - fold_size))

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hovered = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.openRequested.emit(self.note_id)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3d3d3d;
            }
        """)
        open_action = menu.addAction("Open note")
        open_action.triggered.connect(lambda: self.openRequested.emit(self.note_id))

        delete_action = menu.addAction("Delete note")
        delete_action.triggered.connect(lambda: self.deleteRequested.emit(self.note_id))

        menu.exec(event.globalPos())

    def matches_query(self, query: str) -> bool:
        """Check if note title or body contains the search query."""
        if not query:
            return True
        q = query.lower()
        title = (self.note_data.get("title") or "").lower()
        if q in title:
            return True
        plain = get_plain_snippet(self.note_data.get("content", ""), max_chars=1000).lower()
        return q in plain


class NotesListWindow(QWidget):
    """Dedicated Notes List hub window inspired by Microsoft Sticky Notes."""

    DEFAULT_WIDTH = 360
    DEFAULT_HEIGHT = 620
    MIN_WIDTH = 260
    MIN_HEIGHT = 200

    def __init__(self, tray_manager=None, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window,
        )
        self.tray_manager = tray_manager
        self.setWindowTitle("Sticky Notes")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._cards: List[NoteCardWidget] = []
        self._is_dragging = False
        self._drag_start_pos = QPoint()

        self._setup_ui()
        self._restore_geometry()
        self._setup_shortcuts()

    def _setup_ui(self):
        # Outermost layout with gutter for subtle drop shadow
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        self.outer_layout = outer_layout

        # Main dark window container
        self.container = QFrame(self)
        self.container.setObjectName("notesListContainer")
        self.container.setStyleSheet("""
            QFrame#notesListContainer {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 8px;
            }
        """)

        # Soft drop shadow
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(16, 12, 16, 14)
        container_layout.setSpacing(10)
        self.container_layout = container_layout

        # 1. Top action bar (+ on left, ⚙ and ✕ on right)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(6)
        self.top_bar_layout = top_bar

        # New note (+) button
        self.add_btn = FloatingButton("", tone=FloatingButton.Tone.TITLE_BAR, parent=self)
        self.add_btn.setIcon(utils.create_plus_icon("#ffffff", 18))
        self.add_btn.setToolTip("New note (Ctrl+N)")
        self.add_btn.clicked.connect(self._create_new_note)
        top_bar.addWidget(self.add_btn)

        top_bar.addStretch(1)

        # Settings (⚙) button
        self.settings_btn = FloatingButton("", tone=FloatingButton.Tone.TITLE_BAR, parent=self)
        self.settings_btn.setIcon(utils.create_gear_icon("#ffffff", 18))
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self._open_settings)
        top_bar.addWidget(self.settings_btn)

        # Close (✕) button
        self.close_btn = FloatingButton("", tone=FloatingButton.Tone.CLOSE, parent=self)
        self.close_btn.setIcon(utils.create_close_icon("#ffffff", 16))
        self.close_btn.setToolTip("Close (Esc)")
        self.close_btn.clicked.connect(self.close)
        top_bar.addWidget(self.close_btn)

        # Apply flat modern borderless style matching note window
        FloatingButton.apply_theme_to_all(
            (self.add_btn, self.settings_btn, self.close_btn),
            text_color="#ffffff",
            is_dark_theme=True,
        )

        container_layout.addLayout(top_bar)

        # 2. Bold header "Sticky Notes"
        header_label = QLabel("Sticky Notes")
        header_label.setStyleSheet("color: #ffffff; font-size: 19pt; font-weight: bold;")
        self.header_label = header_label
        container_layout.addWidget(header_label)

        # 3. Search Bar with magnifying glass
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setFixedHeight(34)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #383838;
                border-radius: 6px;
                padding-left: 12px;
                padding-right: 32px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
                background-color: #333333;
            }
        """)
        search_icon = utils.create_search_icon("#888888", 16)
        self.search_input.addAction(search_icon, QLineEdit.ActionPosition.TrailingPosition)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        container_layout.addLayout(search_layout)

        # 4. Scroll Area for Note Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #1e1e1e;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #444444;
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #666666;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Container inside scroll area
        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background-color: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 6, 0, 6)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch(1)

        self.scroll_area.setWidget(self.cards_container)
        container_layout.addWidget(self.scroll_area)

        # Empty State Label
        self.empty_label = QLabel("No notes found")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #777777; font-size: 11pt; padding: 40px 0;")
        self.empty_label.hide()
        container_layout.addWidget(self.empty_label)

        # 5. Bottom row with subtle size grip
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 0, 0, 0)
        bottom_bar.addStretch(1)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("background: transparent; width: 14px; height: 14px;")
        bottom_bar.addWidget(self.size_grip)
        container_layout.addLayout(bottom_bar)
        self.bottom_bar_layout = bottom_bar

        outer_layout.addWidget(self.container)

    def _setup_shortcuts(self):
        new_shortcut = QShortcut(QKeySequence(config.SHORTCUTS.get("new_note", "Ctrl+N")), self)
        new_shortcut.activated.connect(self._create_new_note)

        find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        find_shortcut.activated.connect(self._focus_search)

        esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        esc_shortcut.activated.connect(self._handle_esc)

    def _focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _handle_esc(self):
        if self.search_input.text():
            self.search_input.clear()
        else:
            self.close()

    def _adjust_window_geometry(self, preserve_position: bool = True):
        """Adjust window width to 1/4 viewport width, and height to match note entries count
        or full viewport height if note list is long."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            avail_x = avail.x()
            avail_y = avail.y()
            avail_w = avail.width()
            avail_h = avail.height()
        else:
            avail_x, avail_y, avail_w, avail_h = 0, 0, 1440, 810

        # Narrow down width to 1/4 of viewport width
        target_w = max(self.MIN_WIDTH, int(avail_w * 0.25))

        # Chrome height (margins, header, search bar, top action bar, bottom grip)
        chrome_h = (
            self.outer_layout.contentsMargins().top()
            + self.outer_layout.contentsMargins().bottom()
            + self.container_layout.contentsMargins().top()
            + self.container_layout.contentsMargins().bottom()
            + self.top_bar_layout.sizeHint().height()
            + self.header_label.sizeHint().height()
            + self.search_input.sizeHint().height()
            + self.bottom_bar_layout.sizeHint().height()
            + self.container_layout.spacing() * 4
        )

        visible_cards = [c for c in self._cards if not c.isHidden()]
        if not visible_cards:
            content_h = max(70, self.empty_label.sizeHint().height())
        else:
            card_spacing = self.cards_layout.spacing()
            cards_total = sum(c.sizeHint().height() for c in visible_cards)
            cards_total += card_spacing * max(0, len(visible_cards) - 1)
            cards_margins = self.cards_layout.contentsMargins().top() + self.cards_layout.contentsMargins().bottom()
            content_h = cards_total + cards_margins

        total_h = chrome_h + content_h
        min_h = self.MIN_HEIGHT
        max_h = avail_h  # all available height of the viewport

        # Take all available height when note list is very long;
        # otherwise take only as much height as its note entries count.
        target_h = min(max_h, max(min_h, total_h))

        has_pos = (self.x() != 0 or self.y() != 0)
        if preserve_position and (self.isVisible() or has_pos):
            curr_pos = self.pos()
            x = max(avail_x, min(curr_pos.x(), avail_x + avail_w - target_w))
            if target_h >= max_h:
                y = avail_y
            else:
                y = max(avail_y, min(curr_pos.y(), avail_y + avail_h - target_h))
            self.setGeometry(x, y, target_w, target_h)
        else:
            x = avail_x + (avail_w - target_w) // 2
            y = avail_y if target_h >= max_h else avail_y + (avail_h - target_h) // 2
            self.setGeometry(x, y, target_w, target_h)

    def _restore_geometry(self):
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        geo = settings.value("notes_list_window_geometry", None)
        if isinstance(geo, QByteArray) and not geo.isEmpty():
            self.restoreGeometry(geo)
        self._adjust_window_geometry(preserve_position=True)

    def showEvent(self, event):
        super().showEvent(event)
        self._adjust_window_geometry(preserve_position=True)

    def closeEvent(self, event):
        settings = QSettings(config.ORG_NAME, config.APP_NAME)
        settings.setValue("notes_list_window_geometry", self.saveGeometry())
        super().closeEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Allow window dragging from header region
            if event.position().y() <= 100:
                wh = self.windowHandle()
                if wh is not None and wh.startSystemMove():
                    return
                self._is_dragging = True
                self._drag_start_pos = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._is_dragging = False
        super().mouseReleaseEvent(event)

    def update_note_open_state(self, note_id: str, is_open: bool):
        """Immediately update the visual dog-ear folded corner indicator on the card."""
        for card in self._cards:
            if card.note_id == note_id:
                card.set_open(is_open)
                break

    def refresh_notes(self, closed_note_id: str = None):
        """Fetch all notes from SQLite, sort by last_edited, and render cards."""
        db = storage.get_db()
        notes_data = db.get_all_notes()

        # If any open notes in memory have newer unsaved content or titles, merge them
        open_notes_map = self.tray_manager.open_notes if (self.tray_manager and hasattr(self.tray_manager, "open_notes")) else {}
        for item in notes_data:
            nid = item["id"]
            if nid == closed_note_id:
                item["is_open"] = False
            elif nid in open_notes_map:
                open_note = open_notes_map[nid]
                item["title"] = open_note.title
                item["content"] = open_note.text_edit.toHtml()
                item["theme"] = open_note._theme_name
                item["last_edited"] = open_note.last_edited
                is_closing = getattr(open_note, "_is_closing", False) is True
                item["is_open"] = bool(open_note is not None and open_note.isVisible() and not is_closing)
            else:
                item["is_open"] = bool(item.get("is_open", False))

        # Clear existing cards
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        # Re-populate layout
        for note in notes_data:
            card = NoteCardWidget(note, parent=self.cards_container)
            card.openRequested.connect(self._open_note)
            card.deleteRequested.connect(self._confirm_delete_note)
            # Insert before the stretch at the end
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
            self._cards.append(card)

        self._filter_cards()

    def _on_search_changed(self, text: str):
        self._filter_cards()

    def _filter_cards(self):
        query = self.search_input.text().strip()
        visible_count = 0
        for card in self._cards:
            matches = card.matches_query(query)
            card.setVisible(matches)
            if matches:
                visible_count += 1

        if visible_count == 0:
            if not self._cards:
                self.empty_label.setText("No notes yet\nClick + to create your first sticky note")
            else:
                self.empty_label.setText("No notes match your search")
            self.empty_label.show()
            self.scroll_area.hide()
        else:
            self.empty_label.hide()
            self.scroll_area.show()

        self._adjust_window_geometry(preserve_position=True)

    def _create_new_note(self):
        if self.tray_manager and hasattr(self.tray_manager, "_create_new_note"):
            self.tray_manager._create_new_note()
            QTimer.singleShot(100, self.refresh_notes)

    def _open_settings(self):
        if self.tray_manager and hasattr(self.tray_manager, "_show_settings"):
            self.tray_manager._show_settings()

    def _open_note(self, note_id: str):
        self.update_note_open_state(note_id, True)
        if self.tray_manager and hasattr(self.tray_manager, "_focus_note"):
            self.tray_manager._focus_note(note_id)
            QTimer.singleShot(50, self.refresh_notes)

    def _confirm_delete_note(self, note_id: str):
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete Note")
        msg.setText("Are you sure you want to delete this note?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #505050;
                border-radius: 4px;
                padding: 6px 16px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            if self.tray_manager:
                note = self.tray_manager.open_notes.get(note_id)
                if note is not None:
                    note._is_being_deleted = True
                    note.close()
                    note.deleteLater()
                self.tray_manager._handle_note_deletion(note_id)
            self.refresh_notes()
