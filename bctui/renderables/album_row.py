from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text


class AlbumRow:
    def __init__(
        self,
        artist: str,
        title: str,
        playing: bool = False,
        ratio: float = 0.4,
    ):
        self._artist = artist
        self._title = title
        self._playing = playing
        self._ratio = ratio

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        console.options.__eq__
        width = options.max_width
        w1 = round(self._ratio * width)
        w2 = width - w1 - 1

        t1 = Text(self._artist)
        t1.truncate(w1, overflow="ellipsis", pad=True)

        t2 = Text(self._title)
        t2.truncate(w2, overflow="ellipsis", pad=True)

        out = Text(" ").join((t1, t2))
        if self._playing:
            out.stylize("reverse")
        yield out

    @property
    def playing(self) -> bool:
        return self._playing

    @playing.setter
    def playing(self, value: bool) -> None:
        self._playing = value
