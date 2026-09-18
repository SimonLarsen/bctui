import math

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from bctui.format import duration_to_hhmmss


class TrackRow:
    def __init__(
        self,
        track_no: int,
        num_tracks: int,
        title: str,
        artist: str,
        duration: float,
        playing: bool = False,
        show_artist: bool = False,
        ratio: float = 0.4,
    ):
        self._track_no = track_no
        self._num_tracks = num_tracks
        self._title = title
        self._artist = artist
        self._duration = duration
        self._playing = playing
        self._show_artist = show_artist
        self._ratio = ratio

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        width = options.max_width
        no_width = max(math.floor(math.log10(self._num_tracks)) + 2, 2)
        duration_width = 8 if self._duration >= 3600 else 5

        if self._show_artist:
            flex_width = width - no_width - duration_width - 3
            artist_width = round(flex_width * self._ratio)
        else:
            flex_width = width - no_width - duration_width - 2
            artist_width = 0
        title_width = flex_width - artist_width

        elements = []

        text_track = Text(f"{self._track_no + 1}.")
        text_track.pad_left(no_width - text_track.cell_len)
        elements.append(text_track)

        if self._show_artist:
            text_artist = Text(self._artist)
            text_artist.truncate(artist_width, overflow="ellipsis", pad=True)
            elements.append(text_artist)

        text_title = Text(self._title)
        text_title.truncate(title_width, overflow="ellipsis", pad=True)
        elements.append(text_title)

        text_duration = Text(duration_to_hhmmss(self._duration))
        text_duration.pad_left(duration_width - text_duration.cell_len)
        elements.append(text_duration)

        out = Text(" ").join(elements)
        if self._playing:
            out.stylize("reverse")
        yield out
