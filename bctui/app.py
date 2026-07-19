from dataclasses import dataclass
import math
from rich.table import Table
from textual.app import App, ComposeResult
from textual import work
from textual.reactive import reactive
from textual.message import Message
from textual.containers import Horizontal
from textual.binding import Binding
from textual.widgets import OptionList, Footer, ProgressBar
import mpv
from bctui.bandcamp import fetch_album, CollectionEntry, TrackData
from bctui.cache import load_collection


def _duration_to_hhmmss(duration: float) -> str:
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"


class JKOptionList(OptionList):
    BINDINGS = [
        Binding(key="j", action="cursor_down"),
        Binding(key="k", action="cursor_up"),
    ]


class AlbumList(JKOptionList):
    collection: reactive[list[CollectionEntry]] = reactive([])

    @dataclass
    class AlbumSelected(Message):
        artist: str
        album: str
        album_url: str

    def __init__(self):
        super().__init__()
        self.border_title = "Collection"

    def watch_collection(self, collection: list[CollectionEntry]) -> None:
        self.clear_options()

        for elem in collection:
            row = Table.grid(expand=True, padding=(0, 1, 0, 1))
            row.add_column(ratio=2, no_wrap=True)
            row.add_column(ratio=3, no_wrap=True)
            row.add_row(elem.artist, elem.title)
            self.add_option(row)

        self.highlighted = 0
        self.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        album = self.collection[index]
        self.post_message(self.AlbumSelected(album.artist, album.title, album.url))


class TrackList(JKOptionList):
    album_url: reactive[str] = reactive("")
    tracks: reactive[list[TrackData]] = reactive([])

    @dataclass
    class TrackSelected(Message):
        tracks: list[TrackData]
        index: int

    def __init__(self):
        super().__init__()
        self.border_title = "N/A - N/A"

    def watch_tracks(self, tracks: list[TrackData]) -> None:
        self.clear_options()

        if len(tracks) == 0:
            return

        no_width = max(math.ceil(math.log10(len(tracks))) + 1, 2)
        max_duration = max([t.duration for t in tracks])
        duration_width = 8 if max_duration >= 3600 else 5

        for i, track in enumerate(tracks):
            row = Table.grid(expand=True, padding=(0, 1, 0, 1))
            row.add_column(width=no_width, justify="right")
            row.add_column(ratio=1, no_wrap=True)
            row.add_column(width=duration_width, justify="right")
            row.add_row(
                f"{i + 1}.",
                track.title,
                _duration_to_hhmmss(track.duration),
            )
            self.add_option(row)
        self.highlighted = 0

    @work(exclusive=True)
    async def fetch_track_list(self, album_url: str) -> None:
        self.tracks = await fetch_album(album_url)

    async def watch_album_url(self, album_url: str) -> None:
        if album_url == "":
            return
        self.tracks = []
        self.fetch_track_list(album_url)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.post_message(self.TrackSelected(self.tracks, event.option_index))


class BCTUIApp(App):
    CSS_PATH = "style.tcss"

    AUTO_FOCUS = None

    BINDINGS = [
        Binding("F2", "search", "Search"),
        Binding("<", "prev", "Prev"),
        Binding(">", "next", "Next"),
        Binding("p", "pause", "Pause"),
        Binding("h", "focus_collection", "Focus collection"),
        Binding("l", "focus_track_list", "Focus tracks"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield AlbumList()
            yield TrackList()

        yield ProgressBar(total=1.0, show_percentage=True, show_eta=False)
        yield Footer(compact=True)

    def on_mount(self) -> None:
        collection = load_collection()

        album_list = self.query_exactly_one(AlbumList)
        album_list.collection = collection

        self.mpv = mpv.MPV(
            force_seekable=True,
            prefetch_playlist=True,
        )

        self.progress_timer = self.set_interval(1.0, self.update_progress)

    def on_unmount(self) -> None:
        self.mpv.terminate()

    def on_album_list_album_selected(self, message: AlbumList.AlbumSelected) -> None:
        track_list = self.query_exactly_one(TrackList)
        track_list.border_title = f"{message.artist} - {message.album}"
        track_list.album_url = message.album_url

    def on_track_list_track_selected(self, message: TrackList.TrackSelected) -> None:
        self.mpv.stop(keep_playlist=False)
        self.mpv.playlist_clear()
        for track in message.tracks:
            self.mpv.playlist_append(track.url)
        self.mpv.playlist_pos = message.index

    def action_prev(self) -> None:
        pos = self.mpv.playlist_pos
        if not isinstance(pos, int) or pos == -1:
            return
        self._set_playlist_pos(pos - 1)

    def action_next(self) -> None:
        pos = self.mpv.playlist_pos
        if not isinstance(pos, int) or pos == -1:
            return
        self._set_playlist_pos(pos + 1)

    def action_pause(self) -> None:
        self.mpv.pause = not self.mpv.pause

    def action_focus_collection(self) -> None:
        self.query_exactly_one(AlbumList).focus()

    def action_focus_track_list(self) -> None:
        self.query_exactly_one(TrackList).focus()

    def _set_playlist_pos(self, index: int) -> None:
        n = len(self.mpv.playlist_filenames)
        if n == 0:
            return
        self.mpv.playlist_pos = min(max(index, 0), n - 1)

    def update_progress(self) -> None:
        percent_pos = self.mpv.percent_pos
        if percent_pos is None or not isinstance(percent_pos, float):
            return
        self.query_exactly_one(ProgressBar).update(progress=percent_pos / 100.0)


if __name__ == "__main__":
    app = BCTUIApp()
    app.run()
