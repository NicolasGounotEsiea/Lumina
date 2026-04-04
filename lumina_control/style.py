"""Qt stylesheet — generated from the colour palette in config.py."""
from lumina_control.config import (
    ACCENT_COLOR, ACCENT_DIM, ACCENT_SUBTLE,
    BG_COLOR, CARD_COLOR, CARD_HOVER,
    BORDER_COLOR, BORDER_ACCENT,
    TEXT_COLOR, TEXT_MUTED, DANGER_COLOR,
)

STYLESHEET = f"""
    QWidget {{
        color: {TEXT_COLOR};
        font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
        font-size: 13px;
    }}

    /* ── SCROLLBAR ─────────────────────────────── */
    QScrollBar:vertical {{
        background: transparent;
        width: 5px;
        margin: 2px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_ACCENT};
        border-radius: 2px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #3d5070; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

    /* ── MENU ──────────────────────────────────── */
    QMenu {{
        background-color: {CARD_COLOR};
        color: {TEXT_COLOR};
        border: 1px solid {BORDER_ACCENT};
        border-radius: 10px;
        padding: 6px 4px;
    }}
    QMenu::item {{
        padding: 7px 16px;
        border-radius: 6px;
        margin: 1px 4px;
    }}
    QMenu::item:selected {{
        background-color: {BORDER_ACCENT};
        color: {TEXT_COLOR};
    }}
    QMenu::separator {{
        height: 1px;
        background: {BORDER_COLOR};
        margin: 4px 10px;
    }}

    /* ── DIALOG ────────────────────────────────── */
    QDialog {{
        background-color: {BG_COLOR};
        border: 1px solid {BORDER_ACCENT};
    }}

    /* ── CONTAINER PRINCIPAL ───────────────────── */
    QWidget#Container {{
        background-color: {BG_COLOR};
        border-radius: 16px;
        border: 1px solid {BORDER_ACCENT};
    }}

    /* ── SCROLL AREA ───────────────────────────── */
    QScrollArea {{ background: transparent; border: none; }}
    QAbstractScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}

    /* ── CARDS MONITEUR ────────────────────────── */
    QFrame#Card {{
        background-color: {CARD_COLOR};
        border-radius: 12px;
        border: 1px solid {BORDER_COLOR};
    }}

    /* ── LABELS ────────────────────────────────── */
    QLabel#AppTitle {{
        font-weight: 700;
        font-size: 15px;
        color: {TEXT_COLOR};
    }}
    QLabel#AppSubtitle {{
        color: {TEXT_MUTED};
        font-size: 11px;
    }}
    QLabel#Title {{
        font-weight: 600;
        font-size: 14px;
        color: {TEXT_COLOR};
    }}
    QLabel#SectionTitle {{
        font-weight: 700;
        font-size: 10px;
        color: {TEXT_MUTED};
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

    /* ── SLIDERS ───────────────────────────────── */
    QSlider::groove:horizontal {{
        height: 4px;
        background: {BORDER_ACCENT};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {ACCENT_DIM}, stop:1 {ACCENT_COLOR});
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {TEXT_COLOR};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
        border: 2px solid {ACCENT_COLOR};
    }}
    QSlider::handle:horizontal:hover {{
        background: {ACCENT_COLOR};
        border-color: {TEXT_COLOR};
    }}
    QSlider::handle:horizontal:pressed {{
        background: {ACCENT_DIM};
        border-color: {ACCENT_DIM};
    }}

    /* ── SLIDERS RGB ───────────────────────────── */
    QSlider#SliderR::sub-page:horizontal {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #dc2626, stop:1 #f87171);
    }}
    QSlider#SliderG::sub-page:horizontal {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #16a34a, stop:1 #34d399);
    }}
    QSlider#SliderB::sub-page:horizontal {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1d4ed8, stop:1 #60a5fa);
    }}
    QSlider#SliderR::handle:horizontal {{ border-color: #f87171; }}
    QSlider#SliderG::handle:horizontal {{ border-color: #34d399; }}
    QSlider#SliderB::handle:horizontal {{ border-color: #60a5fa; }}

    /* ── BOUTONS GÉNÉRIQUES ────────────────────── */
    QPushButton {{
        background-color: {CARD_COLOR};
        border: 1px solid {BORDER_ACCENT};
        border-radius: 8px;
        padding: 7px 14px;
        color: {TEXT_COLOR};
    }}
    QPushButton:hover {{
        background-color: {CARD_HOVER};
        border-color: {ACCENT_COLOR};
        color: {ACCENT_COLOR};
    }}
    QPushButton:pressed {{ background-color: {BG_COLOR}; }}

    /* ── PILL PRIMARY ──────────────────────────── */
    QPushButton[class="pill"] {{
        background-color: {ACCENT_SUBTLE};
        border: 1px solid rgba(56,189,248,0.25);
        border-radius: 999px;
        padding: 7px 16px;
        color: {ACCENT_COLOR};
        font-weight: 600;
    }}
    QPushButton[class="pill"]:hover {{
        background-color: rgba(56,189,248,0.2);
        border-color: {ACCENT_COLOR};
    }}
    QPushButton[class="pill"]:pressed {{ background-color: rgba(56,189,248,0.06); }}

    /* ── PILL MUTED ────────────────────────────── */
    QPushButton[class="pill-muted"] {{
        background-color: transparent;
        border: 1px solid {BORDER_ACCENT};
        border-radius: 999px;
        padding: 7px 14px;
        color: {TEXT_MUTED};
    }}
    QPushButton[class="pill-muted"]:hover {{
        background-color: {BORDER_COLOR};
        border-color: {TEXT_MUTED};
        color: {TEXT_COLOR};
    }}

    /* ── BOUTONS RAPIDES ───────────────────────── */
    QPushButton[quick="true"] {{
        background-color: {CARD_COLOR};
        border: 1px solid {BORDER_ACCENT};
        border-radius: 999px;
        padding: 7px 16px;
        color: {TEXT_COLOR};
        font-weight: 500;
    }}
    QPushButton[quick="true"]:hover {{
        background-color: {CARD_HOVER};
        border-color: {ACCENT_COLOR};
        color: {ACCENT_COLOR};
    }}
    QPushButton[quick="true"]:pressed {{ background-color: {BG_COLOR}; }}
    QPushButton[quick="true"][class="pill-muted"] {{
        background-color: transparent;
        border: 1px solid {BORDER_COLOR};
        color: {TEXT_MUTED};
    }}
    QPushButton[quick="true"][class="pill-muted"]:hover {{
        background-color: {BORDER_COLOR};
        border-color: {BORDER_ACCENT};
        color: {TEXT_COLOR};
    }}
    QPushButton[quickRole="action"] {{
        border-radius: 10px;
        padding: 6px 12px;
        font-size: 12px;
    }}

    /* ── FOCUS TOGGLE ──────────────────────────── */
    QPushButton#FocusToggle {{
        background-color: {BORDER_COLOR};
        border: 1px solid {BORDER_ACCENT};
        border-radius: 999px;
        padding: 5px 14px;
        color: {TEXT_MUTED};
        font-weight: 600;
        font-size: 12px;
    }}
    QPushButton#FocusToggle:hover {{ border-color: {ACCENT_COLOR}; }}
    QPushButton#FocusToggle:checked {{
        background-color: {ACCENT_SUBTLE};
        border-color: {ACCENT_COLOR};
        color: {ACCENT_COLOR};
    }}

    /* ── ICON BUTTONS ──────────────────────────── */
    QPushButton.icon-btn {{
        border: none;
        background-color: transparent;
        font-size: 16px;
        color: {TEXT_MUTED};
        border-radius: 6px;
        padding: 4px;
    }}
    QPushButton.icon-btn:hover {{
        color: {TEXT_COLOR};
        background-color: {BORDER_ACCENT};
    }}
    QPushButton#PowerBtn[active="false"] {{ color: {DANGER_COLOR}; }}

    /* ── CLOSE & QUIT ──────────────────────────── */
    QPushButton#CloseWinBtn {{
        background: transparent;
        border: none;
        font-size: 13px;
        color: {TEXT_MUTED};
        border-radius: 5px;
        padding: 2px;
    }}
    QPushButton#CloseWinBtn:hover {{
        color: #fff;
        background-color: #c0392b;
    }}
    QPushButton#QuitBtn {{
        background: transparent;
        border: none;
        color: {TEXT_MUTED};
        font-size: 11px;
        padding: 4px 8px;
    }}
    QPushButton#QuitBtn:hover {{ color: {DANGER_COLOR}; }}

    /* ── CHECKBOX ──────────────────────────────── */
    QCheckBox {{
        color: {TEXT_COLOR};
        spacing: 8px;
        font-size: 13px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1.5px solid {BORDER_ACCENT};
        background: {CARD_COLOR};
    }}
    QCheckBox::indicator:hover {{
        border-color: {ACCENT_COLOR};
        background: {CARD_HOVER};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT_COLOR};
        border-color: {ACCENT_COLOR};
    }}
    QCheckBox::indicator:checked:hover {{
        background: {ACCENT_DIM};
        border-color: {ACCENT_DIM};
    }}
    QCheckBox:disabled {{ color: {BORDER_ACCENT}; }}
    QCheckBox::indicator:disabled {{
        border-color: {BORDER_COLOR};
        background: {BG_COLOR};
    }}

    /* ── COMBOBOX ──────────────────────────────── */
    QComboBox {{
        background-color: {CARD_COLOR};
        border: 1px solid {BORDER_ACCENT};
        border-radius: 8px;
        padding: 5px 10px;
        color: {TEXT_COLOR};
    }}
    QComboBox:hover {{ border-color: {ACCENT_COLOR}; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background-color: {CARD_COLOR};
        border: 1px solid {BORDER_ACCENT};
        border-radius: 8px;
        selection-background-color: {BORDER_ACCENT};
        color: {TEXT_COLOR};
        outline: none;
        padding: 4px;
    }}
"""
