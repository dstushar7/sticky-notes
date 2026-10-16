# tests/test_ui_modern.py
import os
import pytest
from unittest.mock import patch, MagicMock

# Force offscreen platform for headless Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QIcon
from stickynotes.note_window import StickyNote, TitleBar, FormatBar
from stickynotes.widgets import FloatingButton
from stickynotes import config, utils


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_title_bar_has_close_button(qapp):
    """TitleBar must have a close_btn with Tone.CLOSE and closeRequested signal."""
    tb = TitleBar()
    assert hasattr(tb, "close_btn")
    assert tb.close_btn is not None
    assert tb.close_btn._tone == FloatingButton.Tone.CLOSE
    assert "Ctrl+W" in tb.close_btn.toolTip()


def test_close_button_emits_close_requested(qapp):
    """Clicking close_btn must emit closeRequested signal."""
    tb = TitleBar()
    mock_slot = MagicMock()
    tb.closeRequested.connect(mock_slot)

    tb.close_btn.click()
    mock_slot.assert_called_once()


def test_note_close_button_closes_and_saves(qapp):
    """Clicking close_btn on StickyNote triggers close and saves data."""
    note = StickyNote(note_id="test-close-id", content="Save before closing")
    note.show()

    with patch.object(note, "_save") as mock_save:
        note.title_bar.close_btn.click()
        mock_save.assert_called_once_with(force=True)
    assert not note.isVisible()


def test_floating_button_flat_modern_style(qapp):
    """FloatingButton must have transparent idle background and no drop shadow."""
    btn = FloatingButton("+", tone=FloatingButton.Tone.TITLE_BAR)
    assert btn.graphicsEffect() is None  # no skeuomorphic drop shadow

    btn.apply_theme("#1a1a1a", is_dark_theme=False)
    qss = btn.styleSheet()
    assert "background-color: transparent" in qss
    assert "border: none" in qss


def test_close_button_hover_style(qapp):
    """Tone.CLOSE button must have red hover background."""
    close_btn = FloatingButton("", tone=FloatingButton.Tone.CLOSE)
    close_btn.apply_theme("#1a1a1a", is_dark_theme=False)
    qss = close_btn.styleSheet()
    assert "rgba(232, 17, 35" in qss or "#e81123" in qss


def test_crisp_icon_generators(qapp):
    """Vector icon helpers must generate non-null icons with high-DPI buffers."""
    for fn in (
        utils.create_plus_icon,
        utils.create_options_icon,
        utils.create_close_icon,
        utils.create_bullet_list_icon,
        utils.create_checklist_icon,
    ):
        icon = fn("#1a1a1a", 24)
        assert isinstance(icon, QIcon)
        assert not icon.isNull()
        sizes = icon.availableSizes()
        assert len(sizes) > 0
        # Check that 4x supersampling backing buffer was generated
        assert sizes[0].width() >= 24

    pin_icon = utils.create_pin_icon("#1a1a1a", 24, filled=True)
    assert isinstance(pin_icon, QIcon)
    assert not pin_icon.isNull()


def test_format_bar_strike_button_label(qapp):
    """FormatBar strike_btn should use modern 'ab' with line-through."""
    fb = FormatBar()
    assert fb.strike_btn.text() == "ab"
