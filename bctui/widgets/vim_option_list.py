from textual.binding import Binding
from textual.widgets import OptionList


class VimOptionList(OptionList):
    BINDINGS = [
        Binding(key="j", action="cursor_down"),
        Binding(key="k", action="cursor_up"),
        Binding(key="space", action="select"),
        Binding(key="g", action="first"),
        Binding(key="G", action="last"),
    ]
