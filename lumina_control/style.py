"""Qt stylesheet — adapts to Windows dark / light mode."""
from lumina_control.config import (
    ACCENT_COLOR, ACCENT_DIM, ACCENT_SUBTLE,
    BG_COLOR, CARD_COLOR, CARD_HOVER,
    BORDER_COLOR, BORDER_ACCENT,
    TEXT_COLOR, TEXT_MUTED,
    DANGER_COLOR, SUCCESS_COLOR,
)


def get_stylesheet(dark: bool = True) -> str:
    """Return the full Qt stylesheet for dark or light mode."""

    if dark:
        ac     = ACCENT_COLOR    # "#60CDFF"
        ad     = ACCENT_DIM      # "#4AB8F0"
        asu    = ACCENT_SUBTLE   # "rgba(96,205,255,0.12)"
        ac_rgb = "96,205,255"    # for rgba(…) usage
        bg     = BG_COLOR        # "#202020"
        card   = CARD_COLOR      # "#2B2B2B"
        chov   = CARD_HOVER      # "#363636"
        bord   = BORDER_COLOR    # "#282828"
        bacc   = BORDER_ACCENT   # "#484848"
        txt    = TEXT_COLOR      # "#F0F0F0"
        mute   = TEXT_MUTED      # "#8A8A8A"
        dang   = DANGER_COLOR    # "#FF6F6F"
        succ   = SUCCESS_COLOR   # "#6CCB5F"
        btn_hover  = "#424242"
        btn_hover2 = "#606060"
        hdr_hover  = "rgba(255,255,255,0.04)"
        hdr_check  = "rgba(255,255,255,0.07)"
        scroll_h   = "#606060"
        sl_handle  = txt         # slider handle fill
        card_top   = chov        # card gradient top
    else:
        # Windows 11 light palette — doux et aéré
        ac     = "#0067C0"
        ad     = "#004E99"
        asu    = "rgba(0,103,192,0.10)"
        ac_rgb = "0,103,192"     # for rgba(…) usage
        bg     = "#EAEAEA"
        card   = "#F8F8F8"
        chov   = "#EDEDED"
        bord   = "#DEDEDE"
        bacc   = "#CACACA"
        txt    = "#1C1C1C"
        mute   = "#717171"
        dang   = "#C42B1C"
        succ   = "#107C10"
        btn_hover  = "#E2E2E2"
        btn_hover2 = "#B8B8B8"
        hdr_hover  = "rgba(0,0,0,0.05)"
        hdr_check  = "rgba(0,0,0,0.08)"
        scroll_h   = "#A8A8A8"
        sl_handle  = "#FFFFFF"   # handle blanc en mode clair
        card_top   = "#FFFFFF"   # légère surbrillance en haut des cartes

    return f"""

/* ═══════════════════════════════════════════════════════════════════════════
   GLOBALS
   ═══════════════════════════════════════════════════════════════════════════ */

QWidget {{
    color: {txt};
    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    font-size: 13px;
    selection-background-color: {ac};
    selection-color: #FFFFFF;
}}

QWidget#MainWindow {{
    background-color: transparent;
}}

/* ═══════════════════════════════════════════════════════════════════════════
   TOOLTIP
   ═══════════════════════════════════════════════════════════════════════════ */

QToolTip {{
    background-color: {card};
    color: {txt};
    border: 1px solid {bacc};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
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
    background: transparent;
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {scroll_h}; }}
QScrollBar::handle:vertical:pressed {{ background: {bacc}; }}
QScrollBar:vertical:hover QScrollBar::handle:vertical {{ background: {bacc}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical,  QScrollBar::sub-page:vertical {{ background: transparent; }}

/* ═══════════════════════════════════════════════════════════════════════════
   MENU
   ═══════════════════════════════════════════════════════════════════════════ */

QMenu {{
    background-color: {card};
    color: {txt};
    border: 1px solid {bacc};
    border-radius: 10px;
    padding: 6px 4px;
}}
QMenu::item {{
    padding: 8px 16px;
    border-radius: 6px;
    margin: 1px 4px;
}}
QMenu::item:selected {{ background-color: {chov}; }}
QMenu::separator {{
    height: 1px;
    background: {bacc};
    margin: 4px 10px;
}}

/* ═══════════════════════════════════════════════════════════════════════════
   DIALOG
   ═══════════════════════════════════════════════════════════════════════════ */

QDialog {{
    background-color: {bg};
    border: 1px solid {bacc};
    border-radius: 12px;
}}

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN CONTAINER & SCROLL AREA
   ═══════════════════════════════════════════════════════════════════════════ */

QWidget#Container {{
    background-color: {bg};
    border-radius: 16px;
    border: 1px solid {bacc};
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

QLabel#AccentIcon {{
    color: {ac};
    font-size: 17px;
    padding: 0;
}}

/* ═══════════════════════════════════════════════════════════════════════════
   BRIGHTNESS STRIP  (global slider card)
   ═══════════════════════════════════════════════════════════════════════════ */

QWidget#BrightnessStrip {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {card_top}, stop:1 {card});
    border-radius: 12px;
    border: 1px solid {bacc};
}}

/* ═══════════════════════════════════════════════════════════════════════════
   MONITOR CARDS
   ═══════════════════════════════════════════════════════════════════════════ */

QFrame#Card {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {card_top}, stop:1 {card});
    border-radius: 12px;
    border: 1px solid {bacc};
}}
QFrame#Card[active="true"] {{
    border: 1px solid {ac};
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {chov}, stop:1 {card});
}}

/* ═══════════════════════════════════════════════════════════════════════════
   LABELS
   ═══════════════════════════════════════════════════════════════════════════ */

QLabel#AppTitle {{
    font-weight: 600;
    font-size: 14px;
    color: {txt};
    letter-spacing: 0.3px;
}}

QLabel#SectionTitle {{
    font-weight: 700;
    font-size: 10px;
    color: {mute};
    letter-spacing: 1.4px;
    padding: 4px 0 2px 0;
}}

QLabel#Title {{
    font-weight: 600;
    font-size: 13px;
    color: {txt};
}}

QLabel#Subtle {{
    color: {mute};
    font-size: 12px;
}}

QLabel#MonitorDetails {{
    color: {mute};
    font-size: 11px;
}}

QLabel#ValueBadge {{
    color: {ac};
    font-size: 12px;
    font-weight: 600;
    min-width: 28px;
}}

QLabel#RuleStatus {{
    font-size: 11px;
    color: {mute};
}}
QLabel#RuleStatus[active="true"] {{
    font-size: 11px;
    color: {ac};
    font-weight: 600;
}}

QLabel#ProcDetect {{
    font-size: 10px;
    color: {mute};
}}
QLabel#ProcDetect[matched="true"] {{
    color: {ac};
}}

QFrame#Separator {{
    background: {bord};
    max-height: 1px;
    border: none;
    margin: 2px 0;
}}

/* ═══════════════════════════════════════════════════════════════════════════
   APP RULES — RULE ROWS
   ═══════════════════════════════════════════════════════════════════════════ */

QFrame#RuleRow {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {card_top}, stop:1 {card});
    border-radius: 8px;
    border: 1px solid {bacc};
}}
QLabel#RuleRowName {{
    font-size: 13px;
    font-weight: 600;
    color: {txt};
}}
QLabel#RuleRowName[rule-enabled="false"] {{
    color: {mute};
}}
QLabel#RuleRowDetail {{
    font-size: 11px;
    color: {mute};
}}

/* ═══════════════════════════════════════════════════════════════════════════
   NAMED PROFILE ROWS
   ═══════════════════════════════════════════════════════════════════════════ */

QWidget#ProfileRow {{
    background-color: {card};
    border-radius: 7px;
    border: 1px solid {bord};
}}
QWidget#ProfileRow:hover {{
    border-color: {bacc};
    background-color: {chov};
}}

/* ═══════════════════════════════════════════════════════════════════════════
   SLIDERS
   ═══════════════════════════════════════════════════════════════════════════ */

QSlider::groove:horizontal {{
    height: 4px;
    background: {bacc};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba({ac_rgb},0.45), stop:1 {ac});
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {sl_handle};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    border: 2px solid {ac};
}}
QSlider::handle:horizontal:hover {{
    background: {sl_handle};
    border-color: {ac};
}}
QSlider::handle:horizontal:pressed {{
    background: {ac};
    border-color: {ad};
}}
QSlider:disabled::groove:horizontal {{
    background: {bord};
}}
QSlider:disabled::sub-page:horizontal {{
    background: rgba({ac_rgb},0.20);
}}
QSlider:disabled::handle:horizontal {{
    border-color: {bacc};
    background: {chov};
}}

/* RGB sliders */
QSlider#SliderR::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #b91c1c, stop:1 #ff6b6b);
}}
QSlider#SliderG::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #166534, stop:1 {succ});
}}
QSlider#SliderB::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1d4ed8, stop:1 {ac});
}}
QSlider#SliderR::handle:horizontal {{ border-color: #ff6b6b; }}
QSlider#SliderG::handle:horizontal {{ border-color: {succ}; }}
QSlider#SliderB::handle:horizontal {{ border-color: {ac}; }}
QSlider#SliderR::handle:horizontal:pressed {{ background: #ff6b6b; border-color: #ff6b6b; }}
QSlider#SliderG::handle:horizontal:pressed {{ background: {succ}; border-color: {succ}; }}

/* Night mode warmth slider */
QSlider#SliderWarmth::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #E8C87A, stop:1 #FF8C00);
}}
QSlider#SliderWarmth::handle:horizontal {{ border-color: #FF8C00; }}
QSlider#SliderWarmth::handle:horizontal:hover {{ background: #FF8C00; border-color: #FF8C00; }}

/* ═══════════════════════════════════════════════════════════════════════════
   BUTTONS  (generic)
   ═══════════════════════════════════════════════════════════════════════════ */

QPushButton {{
    background-color: {chov};
    border: 1px solid {bacc};
    border-radius: 8px;
    padding: 7px 14px;
    color: {txt};
    outline: none;
}}
QPushButton:hover {{
    background-color: {btn_hover};
    border-color: {btn_hover2};
}}
QPushButton:pressed {{ background-color: {card}; border-color: {bacc}; }}
QPushButton:disabled {{
    color: {mute};
    background-color: {card};
    border-color: {bord};
}}

/* ─── Pill primary ─────────────────────────────────────────────────────── */
QPushButton[class="pill"] {{
    background-color: {asu};
    border: 1px solid rgba({ac_rgb},0.30);
    border-radius: 999px;
    padding: 7px 18px;
    color: {ac};
    font-weight: 600;
}}
QPushButton[class="pill"]:hover {{
    background-color: rgba({ac_rgb},0.18);
    border-color: {ac};
}}
QPushButton[class="pill"]:pressed  {{
    background-color: rgba({ac_rgb},0.08);
    border-color: rgba({ac_rgb},0.50);
}}
QPushButton[class="pill"]:disabled {{
    background-color: transparent;
    border-color: {bord};
    color: {mute};
}}

/* ─── Pill muted ──────────────────────────────────────────────────────── */
QPushButton[class="pill-muted"] {{
    background-color: transparent;
    border: 1px solid {bacc};
    border-radius: 999px;
    padding: 7px 14px;
    color: {mute};
}}
QPushButton[class="pill-muted"]:hover {{
    background-color: {chov};
    border-color: {btn_hover2};
    color: {txt};
}}
QPushButton[class="pill-muted"]:pressed {{
    background-color: {card};
    border-color: {bacc};
}}
QPushButton[class="pill-muted"]:disabled {{
    color: {mute};
    border-color: {bord};
    opacity: 0.5;
}}

/* ─── Collapsible header ───────────────────────────────────────────────── */
QPushButton#CollapsibleHeader {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 9px 8px;
    color: {mute};
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 1.2px;
    text-align: left;
}}
QPushButton#CollapsibleHeader:hover {{
    background-color: {hdr_hover};
    color: {txt};
}}
QPushButton#CollapsibleHeader:checked {{
    color: {txt};
}}
QPushButton#CollapsibleHeader:pressed {{
    background-color: {hdr_check};
}}

/* ─── Focus toggle (pill checkable) ───────────────────────────────────── */
QPushButton#FocusToggle {{
    background-color: transparent;
    border: 1px solid {bacc};
    border-radius: 999px;
    padding: 5px 16px;
    color: {mute};
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#FocusToggle:hover {{
    border-color: {btn_hover2};
    color: {txt};
    background-color: {hdr_hover};
}}
QPushButton#FocusToggle:checked {{
    background-color: {asu};
    border-color: {ac};
    color: {ac};
}}

/* ─── Icon buttons ────────────────────────────────────────────────────── */
QPushButton[class="icon-btn"] {{
    border: none;
    background-color: transparent;
    font-size: 15px;
    color: {mute};
    border-radius: 6px;
    padding: 4px;
}}
QPushButton[class="icon-btn"]:hover {{
    color: {txt};
    background-color: {hdr_check};
}}
QPushButton[class="icon-btn"]:pressed {{
    background-color: {bacc};
}}
QPushButton[class="icon-btn"][danger="true"]:hover {{
    color: {dang};
    background-color: rgba(255,111,111,0.10);
}}
QPushButton#PowerBtn[active="false"]         {{ color: {dang}; }}
QPushButton#PowerBtn[active="true"]:hover    {{ color: {succ}; }}

/* ─── Window chrome buttons ───────────────────────────────────────────── */
QPushButton#CloseWinBtn {{
    background: transparent;
    border: none;
    font-size: 11px;
    color: {mute};
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
    color: {mute};
    font-size: 11px;
    padding: 6px 14px;
    border-radius: 6px;
}}
QPushButton#QuitBtn:hover {{
    color: {dang};
    background-color: rgba(255,111,111,0.08);
}}

/* ═══════════════════════════════════════════════════════════════════════════
   LINEEDIT
   ═══════════════════════════════════════════════════════════════════════════ */

QLineEdit {{
    background-color: {card};
    border: 1px solid {bacc};
    border-radius: 8px;
    padding: 6px 10px;
    color: {txt};
}}
QLineEdit:focus {{
    border-color: {ac};
    background-color: {card_top};
}}
QLineEdit:disabled {{
    color: {mute};
    background-color: {chov};
}}

/* ═══════════════════════════════════════════════════════════════════════════
   CHECKBOXES
   ═══════════════════════════════════════════════════════════════════════════ */

QCheckBox {{
    color: {txt};
    spacing: 10px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1.5px solid {bacc};
    background: {chov};
}}
QCheckBox::indicator:hover {{
    border-color: {ac};
    background: {btn_hover};
}}
QCheckBox::indicator:checked {{
    background: {ac};
    border-color: {ac};
}}
QCheckBox::indicator:checked:hover {{
    background: {ad};
    border-color: {ad};
}}
QCheckBox:disabled                  {{ color: {mute}; }}
QCheckBox::indicator:disabled {{
    border-color: {bord};
    background: {bg};
}}

/* ═══════════════════════════════════════════════════════════════════════════
   COMBOBOX
   ═══════════════════════════════════════════════════════════════════════════ */

QComboBox {{
    background-color: {chov};
    border: 1px solid {bacc};
    border-radius: 8px;
    padding: 5px 12px;
    color: {txt};
    min-height: 28px;
}}
QComboBox:hover  {{ border-color: {btn_hover2}; }}
QComboBox:focus  {{ border-color: {ac}; }}
QComboBox:disabled {{ color: {mute}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {card};
    border: 1px solid {bacc};
    border-radius: 8px;
    selection-background-color: {chov};
    color: {txt};
    outline: none;
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{ padding: 6px 10px; border-radius: 4px; }}
QComboBox QAbstractItemView::item:hover   {{ background-color: {chov}; }}
QComboBox QAbstractItemView::item:selected {{
    background-color: {asu};
    color: {ac};
}}

"""


# Backward-compat alias used by __main__.py
STYLESHEET = get_stylesheet(dark=True)
