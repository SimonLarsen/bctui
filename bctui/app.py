import math
from rich.table import Table
from textual.app import App, ComposeResult
from textual import work
from textual.reactive import reactive
from textual.message import Message
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Input, OptionList, Rule
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


class AlbumList(Vertical):
    collection: reactive[list[CollectionEntry]] = reactive([], recompose=True)

    class AlbumSelected(Message):
        def __init__(
            self,
            artist: str,
            album: str,
            album_url: str,
        ) -> None:
            self.artist = artist
            self.album = album
            self.album_url = album_url
            super().__init__()

    def __init__(self):
        super().__init__(classes="column")
        self.border_title = "Collection"

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search", compact=True, max_length=10)

        yield Rule()

        options = OptionList(compact=True)
        for elem in self.collection:
            row = Table.grid(expand=True, padding=(0, 1, 0, 1))
            row.add_column(ratio=2, no_wrap=True)
            row.add_column(ratio=3, no_wrap=True)
            row.add_row(elem.artist, elem.title)
            options.add_option(row)
        options.highlighted = 0
        yield options

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        album = self.collection[index]
        self.post_message(self.AlbumSelected(album.artist, album.title, album.url))


class TrackList(Vertical):
    artist: reactive[str] = reactive("N/A", recompose=True)
    album: reactive[str] = reactive("N/A", recompose=True)
    album_url: reactive[str] = reactive("")
    tracks: reactive[list[TrackData]] = reactive([], recompose=True)

    def __init__(self):
        super().__init__(classes="column")
        self.border_title = "Track list"

    def compose(self) -> ComposeResult:
        yield Label(f"{self.artist} - {self.album}")
        yield Rule()

        if len(self.tracks) == 0:
            return

        no_width = math.ceil(math.log10(len(self.tracks))) + 1
        max_duration = max([t.duration for t in self.tracks])
        duration_width = 8 if max_duration >= 3600 else 5
        
        options = OptionList(compact=True)
        for i, track in enumerate(self.tracks):
            row = Table.grid(expand=True, padding=(0, 1, 0, 1))
            row.add_column(width=no_width, justify="right")
            row.add_column(ratio=1, no_wrap=True)
            row.add_column(width=duration_width, justify="right")
            row.add_row(
                f"{i + 1}.",
                track.title,
                _duration_to_hhmmss(track.duration),
            )
            options.add_option(row)
        options.highlighted = 0
        yield options

    @work(exclusive=True)
    async def fetch_track_list(self, album_url: str) -> None:
        self.tracks = await fetch_album(album_url)

    async def watch_album_url(
        self,
        old_album_url: str,
        new_album_url: str,
    ) -> None:
        if new_album_url == "":
            return
        self.tracks = []
        self.fetch_track_list(new_album_url)


class BCTUIApp(App):
    CSS_PATH = "style.tcss"

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield AlbumList()
            yield TrackList()

    def on_mount(self) -> None:
        collection = load_collection()
        self.query_exactly_one(AlbumList).collection = collection

    def on_album_list_album_selected(self, message: AlbumList.AlbumSelected) -> None:
        track_list = self.query_exactly_one(TrackList)
        track_list.artist = message.artist
        track_list.album = message.album
        track_list.album_url = message.album_url


if __name__ == "__main__":
    app = BCTUIApp()
    app.run()
