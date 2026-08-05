from textual.binding import Binding
from textual.widgets import OptionList


class VimOptionList(OptionList):
    DEFAULT_CSS = """
    VimOptionList {
        background: $background;
        background-tint: $background;
        scrollbar-size: 1 1;
    }
    """

    BINDINGS = [
        Binding(key="j", action="cursor_down"),
        Binding(key="k", action="cursor_up"),
        Binding(key="space", action="select"),
        Binding(key="g", action="first"),
        Binding(key="G", action="last"),
        Binding(key="ctrl+f", action="page_down"),
        Binding(key="ctrl+b", action="page_up"),
    ]
