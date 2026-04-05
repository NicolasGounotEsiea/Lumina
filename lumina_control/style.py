"""Qt stylesheet — Windows 11 Fluent dark theme."""
from lumina_control.config import (
    ACCENT_COLOR, ACCENT_DIM, ACCENT_SUBTLE,
    BG_COLOR, CARD_COLOR, CARD_HOVER,
    BORDER_COLOR, BORDER_ACCENT,
    TEXT_COLOR, TEXT_MUTED,
    DANGER_COLOR, SUCCESS_COLOR,
)

STYLESHEET = f"""

/* ═══════════════════════════════════════════════════════════════════════════
   GLOBALS
   ═══════════════════════════════════════════════════════════════════════════ */

QWidget {{
    color: {TEXT_COLOR};
    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    font-size: 13px;
    selection-background-color: {ACCENT_COLOR};
    selection-color: {BG_COLOR};
}}

/* ═══════════════════════════════════════════════════════════════════════════
   SCROLLBAR
   ═══════════════════════════════════════════════════════════════════════════ */

QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_ACCENT};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: #606060; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical,  QScrollBar::sub-page:vertical {{ background: transparent; }}

/* ═══════════════════════════════════════════════════════════════════════════
   MENU
   ═══════════════════════════════════════════════════════════════════════════ */

QMenu {{
    background-color: {CARD_COLOR};
    color: {TEXT_COLOR};
    border: 1px solid {BORDER_ACCENT};
    border-radius: 10px;
    padding: 6px 4px;
}}
QMenu::item {{
    padding: 8px 16px;
    border-radius: 6px;
    margin: 1px 4px;
}}
QMenu::item:selected {{ background-color: {CARD_HOVER}; }}
QMenu::separator {{
    height: 1px;
    background: {BORDER_ACCENT};
    margin: 4px 10px;
}}

/* ═══════════════════════════════════════════════════════════════════════════
   DIALOG
   ═══════════════════════════════════════════════════════════════════════════ */

QDialog {{
    background-color: {BG_COLOR};
    border: 1px solid {BORDER_ACCENT};
    border-radius: 12px;
}}

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN CONTAINER & SCROLL AREA
   ═══════════════════════════════════════════════════════════════════════════ */

QWidget#Container {{
    background-color: {BG_COLOR};
    border-radius: 16px;
    border: 1px solid {BORDER_ACCENT};
}}

QScrollArea                          {{ background: transparent; border: none; }}
QAbstractScrollArea                  {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget      {{ background: transparent; }}

/* ═══════════════════════════════════════════════════════════════════════════
   TITLE BAR
   ═══════════════════════════════════════════════════════════════════════════ */

QWidget#TitleBar {{
    background-color: transparent;
}}

/* ═══════════════════════════════════════════════════════════════════════════
   BRIGHTNESS STRIP  (global slider card)
   ═══════════════════════════════════════════════════════════════════════════ */

QWidget#BrightnessStrip {{
    background-color: {CARD_COLOR};
    border-radius: 12px;
    border: 1px solid {BORDER_ACCENT};
}}

/* ═══════════════════════════════════════════════════════════════════════════
   MONITOR CARDS
   ═══════════════════════════════════════════════════════════════════════════ */

QFrame#Card {{
    background-color: {CARD_COLOR};
    border-radius: 12px;
    border: 1px solid {BORDER_ACCENT};
}}

/* ═══════════════════════════════════════════════════════════════════════════
   LABELS
   ═══════════════════════════════════════════════════════════════════════════ */

QLabel#AppTitle {{
    font-weight: 600;
    font-size: 14px;
    color: {TEXT_COLOR};
    letter-spacing: 0.2px;
}}

QLabel#SectionTitle {{
    font-weight: 600;
    font-size: 10px;
    color: {TEXT_MUTED};
    letter-spacing: 1.2px;
    padding: 2px 0;
}}

QLabel#Title {{
    font-weight: 600;
    font-size: 13px;
    color: {TEXT_COLOR};
}}

QLabel#Subtle {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}

QLabel#MonitorDetails {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}

QLabel#ValueBadge {{
    color: {ACCENT_COLOR};
    font-size: 12px;
    font-weight: 600;
}}

/* ═══════════════════════════════════════════════════════════════════════════
   SLIDERS
   ═══════════════════════════════════════════════════════════════════════════ */

QSlider::groove:horizontal {{
    height: 5px;
    background: {BORDER_ACCENT};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {ACCENT_DIM}, stop:1 {ACCENT_COLOR});
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {TEXT_COLOR};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    border: 2px solid {ACCENT_COLOR};
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_COLOR};
    border-color: white;
}}
QSlider::handle:horizontal:pressed {{
    background: {ACCENT_DIM};
    border-color: {ACCENT_DIM};
}}

/* RGB sliders */
QSlider#SliderR::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #b91c1c, stop:1 #ff6b6b);
}}
QSlider#SliderG::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #166534, stop:1 {SUCCESS_COLOR});
}}
QSlider#SliderB::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1d4ed8, stop:1 {ACCENT_COLOR});
}}
QSlider#SliderR::handle:horizontal {{ border-color: #ff6b6b; }}
QSlider#SliderG::handle:horizontal {{ border-color: {SUCCESS_COLOR}; }}
QSlider#SliderB::handle:horizontal {{ border-color: {ACCENT_COLOR}; }}

/* ═══════════════════════════════════════════════════════════════════════════
   BUTTONS  (generic)
   ═══════════════════════════════════════════════════════════════════════════ */

QPushButton {{
    background-color: {CARD_HOVER};
    border: 1px solid {BORDER_ACCENT};
    border-radius: 8px;
    padding: 7px 14px;
    color: {TEXT_COLOR};
    outline: none;
}}
QPushButton:hover {{
    background-color: #424242;
    border-color: #606060;
}}
QPushButton:pressed {{ background-color: {CARD_COLOR}; }}
QPushButton:disabled {{
    color: #4A4A4A;
    background-color: {CARD_COLOR};
    border-color: {BORDER_COLOR};
}}

/* ─── Pill primary ─────────────────────────────────────────────────────── */
QPushButton[class="pill"] {{
    background-color: {ACCENT_SUBTLE};
    border: 1px solid rgba(96,205,255,0.30);
    border-radius: 999px;
    padding: 7px 18px;
    color: {ACCENT_COLOR};
    font-weight: 600;
}}
QPushButton[class="pill"]:hover {{
    background-color: rgba(96,205,255,0.20);
    border-color: {ACCENT_COLOR};
}}
QPushButton[class="pill"]:pressed  {{ background-color: rgba(96,205,255,0.07); }}
QPushButton[class="pill"]:disabled {{
    background-color: transparent;
    border-color: {BORDER_COLOR};
    color: #4A4A4A;
}}

/* ─── Pill muted ──────────────────────────────────────────────────────── */
QPushButton[class="pill-muted"] {{
    background-color: transparent;
    border: 1px solid {BORDER_ACCENT};
    border-radius: 999px;
    padding: 7px 14px;
    color: {TEXT_MUTED};
}}
QPushButton[class="pill-muted"]:hover {{
    background-color: {CARD_HOVER};
    border-color: #606060;
    color: {TEXT_COLOR};
}}
QPushButton[class="pill-muted"]:disabled {{
    color: #4A4A4A;
    border-color: {BORDER_COLOR};
}}

/* ─── Collapsible header ───────────────────────────────────────────────── */
QPushButton#CollapsibleHeader {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 9px 8px;
    color: {TEXT_MUTED};
    font-weight: 600;
    font-size: 10px;
    letter-spacing: 1px;
    text-align: left;
}}
QPushButton#CollapsibleHeader:hover {{
    background-color: rgba(255,255,255,0.04);
    color: {TEXT_COLOR};
}}
QPushButton#CollapsibleHeader:checked {{
    color: {TEXT_COLOR};
}}

/* ─── Focus toggle (pill checkable) ───────────────────────────────────── */
QPushButton#FocusToggle {{
    background-color: transparent;
    border: 1px solid {BORDER_ACCENT};
    border-radius: 999px;
    padding: 5px 16px;
    color: {TEXT_MUTED};
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#FocusToggle:hover {{
    border-color: #606060;
    color: {TEXT_COLOR};
    background-color: rgba(255,255,255,0.04);
}}
QPushButton#FocusToggle:checked {{
    background-color: {ACCENT_SUBTLE};
    border-color: {ACCENT_COLOR};
    color: {ACCENT_COLOR};
}}

/* ─── Icon buttons ────────────────────────────────────────────────────── */
QPushButton[class="icon-btn"] {{
    border: none;
    background-color: transparent;
    font-size: 15px;
    color: {TEXT_MUTED};
    border-radius: 6px;
    padding: 4px;
}}
QPushButton[class="icon-btn"]:hover {{
    color: {TEXT_COLOR};
    background-color: rgba(255,255,255,0.07);
}}
QPushButton#PowerBtn[active="false"]         {{ color: {DANGER_COLOR}; }}
QPushButton#PowerBtn[active="true"]:hover    {{ color: {SUCCESS_COLOR}; }}

/* ─── Window chrome buttons ───────────────────────────────────────────── */
QPushButton#CloseWinBtn {{
    background: transparent;
    border: none;
    font-size: 11px;
    color: {TEXT_MUTED};
    border-radius: 6px;
    padding: 4px 6px;
    min-width: 26px;
}}
QPushButton#CloseWinBtn:hover {{
    color: white;
    background-color: #C42B1C;
}}

QPushButton#QuitBtn {{
    background: transparent;
    border: none;
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 6px 14px;
    border-radius: 6px;
}}
QPushButton#QuitBtn:hover {{
    color: {DANGER_COLOR};
    background-color: rgba(255,111,111,0.08);
}}

/* ═══════════════════════════════════════════════════════════════════════════
   CHECKBOXES
   ═══════════════════════════════════════════════════════════════════════════ */

QCheckBox {{
    color: {TEXT_COLOR};
    spacing: 10px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1.5px solid {BORDER_ACCENT};
    background: {CARD_HOVER};
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT_COLOR};
    background: #424242;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT_COLOR};
    border-color: {ACCENT_COLOR};
}}
QCheckBox::indicator:checked:hover {{
    background: {ACCENT_DIM};
    border-color: {ACCENT_DIM};
}}
QCheckBox:disabled                  {{ color: #4A4A4A; }}
QCheckBox::indicator:disabled {{
    border-color: {BORDER_COLOR};
    background: {BG_COLOR};
}}

/* ═══════════════════════════════════════════════════════════════════════════
   COMBOBOX
   ═══════════════════════════════════════════════════════════════════════════ */

QComboBox {{
    background-color: {CARD_HOVER};
    border: 1px solid {BORDER_ACCENT};
    border-radius: 8px;
    padding: 5px 12px;
    color: {TEXT_COLOR};
    min-height: 28px;
}}
QComboBox:hover  {{ border-color: #606060; }}
QComboBox:focus  {{ border-color: {ACCENT_COLOR}; }}
QComboBox:disabled {{ color: #4A4A4A; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {CARD_COLOR};
    border: 1px solid {BORDER_ACCENT};
    border-radius: 8px;
    selection-background-color: {CARD_HOVER};
    color: {TEXT_COLOR};
    outline: none;
    padding: 4px;
}}
QComboBox QAbstractItemView::item:hover   {{ background-color: {CARD_HOVER}; }}
QComboBox QAbstractItemView::item:selected {{
    background-color: rgba(96,205,255,0.15);
}}

"""
