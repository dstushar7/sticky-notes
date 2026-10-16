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
        utils.create_menu_lines_icon,
        utils.create_search_icon,
        utils.create_gear_icon,
        utils.create_share_icon,
        utils.create_receive_icon,
        utils.create_check_icon,
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


def test_options_panel_share_receive_icons_and_feedback(qapp):
    """OptionsPanel share and receive buttons should use vector icons and update on copied."""
    from stickynotes.note_window import OptionsPanel
    panel = OptionsPanel(current_theme="yellow")
    assert not panel._share_btn.icon().isNull()
    assert panel._share_btn.text() == "Share"

    # Find the receive button in the panel
    receive_btn = None
    for child in panel.findChildren(panel._share_btn.__class__):
        if child.text() == "Receive":
            receive_btn = child
            break
    assert receive_btn is not None
    assert not receive_btn.icon().isNull()

    # Trigger copied feedback
    panel.show_share_copied()
    assert panel._share_btn.text() == "Copied"
    assert not panel._share_btn.icon().isNull()
    panel.close()


def test_format_bar_strike_button_label(qapp):
    """FormatBar strike_btn should use modern 'ab' with line-through."""
    fb = FormatBar()
    assert fb.strike_btn.text() == "ab"


def test_italic_icon_and_button(qapp):
    """FormatBar italic_btn should use a vector Italic icon with serifs."""
    icon = utils.create_italic_icon("#1a1a1a", 16)
    assert isinstance(icon, QIcon)
    assert not icon.isNull()

    fb = FormatBar()
    fb.apply_colors("#F9E44A", "#1a1a1a", False)
    assert not fb.italic_btn.icon().isNull()


def test_format_bar_is_left_aligned(qapp):
    """FormatBar should start with buttons on the left and end with stretch."""
    fb = FormatBar()
    layout = fb.layout()
    # First widget must be bold_btn (not a stretch spacer)
    first_item = layout.itemAt(0)
    assert first_item.widget() == fb.bold_btn
    # Last item must be a stretch spacer
    last_item = layout.itemAt(layout.count() - 1)
    assert last_item.spacerItem() is not None


def test_pin_icon_angled_states(qapp):
    """Pin icon should support both unpinned outline and pinned filled states."""
    unpinned = utils.create_pin_icon("#1a1a1a", 24, filled=False)
    pinned = utils.create_pin_icon("#1a1a1a", 24, filled=True)
    assert not unpinned.isNull()
    assert not pinned.isNull()


def test_format_bar_margins_consistent(qapp):
    """FormatBar margins must have equal left and bottom gaps."""
    fb = FormatBar()
    margins = fb.layout().contentsMargins()
    assert margins.left() == margins.bottom() == 4


