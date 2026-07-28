import math

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text


def _duration_to_hhmmss(duration: float) -> str:
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"


class TrackRow:
    def __init__(
        self,
        track_no: int,
        num_tracks: int,
        title: str,
        duration: float,
        playing: bool = False,
    ):
        self._track_no = track_no
        self._num_tracks = num_tracks
        self._title = title
        self._duration = duration
        self._playing = playing

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        width = options.max_width
        no_width = max(math.floor(math.log10(self._num_tracks)) + 2, 2)
        duration_width = 8 if self._duration >= 3600 else 5
        track_width = width - no_width - duration_width - 2

        t1 = Text(f"{self._track_no + 1}.")
        t1.pad_left(no_width - t1.cell_len)

        t2 = Text(self._title)
        t2.truncate(track_width, overflow="ellipsis", pad=True)

        t3 = Text(_duration_to_hhmmss(self._duration))
        t3.pad_left(duration_width - t3.cell_len)

        out = Text(" ").join((t1, t2, t3))
        if self._playing:
            out.stylize("reverse")
        yield out
