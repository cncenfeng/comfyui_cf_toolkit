"""Help loader — reads Markdown help files from web/help/ directory."""
import os

_HELP_DIR = os.path.join(os.path.dirname(__file__), "web", "help")


def _read_help(node_name, lang):
    path = os.path.join(_HELP_DIR, f"{node_name}.{lang}.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def get_help_en(node_name):
    return _read_help(node_name, "en")


def get_help_zh(node_name):
    return _read_help(node_name, "zh")
