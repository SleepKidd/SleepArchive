from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication


LIGHT = {
    "bg": "#F5F7FB",
    "surface": "#FFFFFF",
    "surface2": "#EEF2F7",
    "text": "#172033",
    "muted": "#667085",
    "border": "#E2E8F0",
    "accent": "#6C5CE7",
    "accent_hover": "#5948D8",
    "accent_soft": "#EEEAFE",
    "success": "#17A673",
    "warning": "#D97706",
    "danger": "#D92D20",
}

DARK = {
    "bg": "#10131A",
    "surface": "#191E28",
    "surface2": "#232A36",
    "text": "#F3F5F8",
    "muted": "#A7B0C0",
    "border": "#303847",
    "accent": "#8B7CF6",
    "accent_hover": "#9E92FA",
    "accent_soft": "#292447",
    "success": "#35C493",
    "warning": "#F3A83B",
    "danger": "#F97066",
}


def is_system_dark(app: QApplication) -> bool:
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def apply_theme(app: QApplication, theme: str) -> dict[str, str]:
    dark = theme == "dark" or (theme == "system" and is_system_dark(app))
    colors = DARK if dark else LIGHT
    app.setStyle("Fusion")
    app.setStyleSheet(_stylesheet(colors))
    app.setProperty("themeName", "dark" if dark else "light")
    return colors


def _stylesheet(c: dict[str, str]) -> str:
    return f"""
    * {{
        font-family: "Segoe UI Variable", "Segoe UI";
        font-size: 10pt;
        color: {c['text']};
    }}
    QMainWindow, QDialog, QWidget#AppRoot, QWidget#Page {{ background: {c['bg']}; }}
    QWidget#Sidebar {{ background: {c['surface']}; border-right: 1px solid {c['border']}; }}
    QLabel#Brand {{ font-size: 18pt; font-weight: 700; color: {c['text']}; }}
    QLabel#PageTitle {{ font-size: 24pt; font-weight: 700; }}
    QLabel#SectionTitle {{ font-size: 14pt; font-weight: 650; }}
    QLabel#Muted, QLabel[muted="true"] {{ color: {c['muted']}; }}
    QLabel#Metric {{ font-size: 18pt; font-weight: 700; }}
    QFrame#Card, QFrame#RuleCard, QFrame#EmptyState, QFrame#ProgressPanel {{
        background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px;
    }}
    QFrame#AccentCard {{
        background: {c['accent_soft']}; border: 1px solid {c['accent']}; border-radius: 16px;
    }}
    QPushButton {{
        min-height: 36px; padding: 0 15px; border: 1px solid {c['border']};
        border-radius: 9px; background: {c['surface']}; font-weight: 600;
    }}
    QPushButton:hover {{ background: {c['surface2']}; border-color: {c['muted']}; }}
    QPushButton:pressed {{ padding-top: 2px; }}
    QPushButton[primary="true"] {{ color: white; background: {c['accent']}; border-color: {c['accent']}; }}
    QPushButton[primary="true"]:hover {{ background: {c['accent_hover']}; }}
    QPushButton[danger="true"] {{ color: {c['danger']}; border-color: {c['danger']}; }}
    QPushButton#NavButton {{
        border: none; text-align: left; padding: 0 14px; min-height: 42px;
        background: transparent; color: {c['muted']};
    }}
    QPushButton#NavButton:hover {{ background: {c['surface2']}; color: {c['text']}; }}
    QPushButton#NavButton:checked {{ background: {c['accent_soft']}; color: {c['accent']}; }}
    QLineEdit, QSpinBox, QComboBox {{
        min-height: 36px; padding: 0 10px; background: {c['surface']};
        border: 1px solid {c['border']}; border-radius: 8px;
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {c['accent']}; }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; }}
    QProgressBar {{
        min-height: 8px; max-height: 8px; border: none; border-radius: 4px; background: {c['surface2']};
    }}
    QProgressBar::chunk {{ border-radius: 4px; background: {c['accent']}; }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QToolButton {{ border: none; border-radius: 7px; padding: 6px; background: transparent; }}
    QToolButton:hover {{ background: {c['surface2']}; }}
    QTabBar::tab {{ padding: 8px 16px; border-radius: 8px; color: {c['muted']}; }}
    QTabBar::tab:selected {{ background: {c['accent_soft']}; color: {c['accent']}; }}
    QTableView {{
        background: {c['surface']}; alternate-background-color: {c['surface2']};
        border: 1px solid {c['border']}; border-radius: 10px; gridline-color: {c['border']};
    }}
    QHeaderView::section {{ background: {c['surface2']}; padding: 8px; border: none; }}
    QMessageBox {{ background: {c['surface']}; }}
    """
