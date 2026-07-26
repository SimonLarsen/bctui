from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text


class AlbumRow:
    def __init__(
        self,
        artist: str,
        title: str,
        ratio: float = 0.4,
    ):
        self._artist = artist
        self._title = title
        self._ratio = ratio

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        width = options.max_width
        w1 = round(self._ratio * width)
        w2 = width - w1 - 1

        t1 = Text(self._artist)
        t1.truncate(w1, overflow="ellipsis", pad=True)
        t2 = Text(self._title)
        t2.truncate(w2, overflow="ellipsis", pad=True)
        yield Text(" ").join((t1, t2))
