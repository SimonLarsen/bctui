from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static

from bctui.format import duration_to_hhmmss


class StatusBar(Horizontal):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
    }

    .statusbar--info {
        width: auto;
        color: $primary;
    }

    .statusbar--separator {
        width: auto;
    }

    .statusbar--time {
        width: 1fr;
        text-align: right;
    }
    """

    title: reactive[str | None] = reactive(None, recompose=True)
    artist: reactive[str | None] = reactive(None, recompose=True)
    album: reactive[str | None] = reactive(None, recompose=True)
    position: reactive[float] = reactive(0.0, recompose=True)
    duration: reactive[float] = reactive(0.0, recompose=True)

    def compose(self) -> ComposeResult:
        if self.title is not None:
            yield Static(self.title, classes="statusbar--info")

            if self.artist is not None:
                yield Static(" by ", classes="statusbar--separator")
                yield Static(self.artist, classes="statusbar--info")

            if self.album is not None:
                yield Static(" from ", classes="statusbar--separator")
                yield Static(self.album, classes="statusbar--info")

        t1 = duration_to_hhmmss(self.position)
        t2 = duration_to_hhmmss(self.duration)
        yield Static(f"[{t1}/{t2}]", classes="statusbar--time")
