from typing import Iterable
from dataclasses import dataclass
from textual.app import App, ComposeResult, SystemCommand
from textual import work
from textual.reactive import reactive
from textual.message import Message
from textual.containers import Horizontal
from textual.binding import Binding
from textual.widgets import OptionList, Footer, ProgressBar, Label
from textual.screen import Screen, ModalScreen
import mpv
from bctui.config import Config
from bctui.types import CollectionEntry, TrackData
from bctui.subsonic import SubsonicClient
from bctui.cache import load_collection, save_collection
from bctui.renderables import AlbumRow, TrackRow


class JKOptionList(OptionList):
    BINDINGS = [
        Binding(key="j", action="cursor_down"),
        Binding(key="k", action="cursor_up"),
    ]


class AlbumList(JKOptionList):
    collection: reactive[list[CollectionEntry]] = reactive([])

    @dataclass
    class AlbumSelected(Message):
        uid: str
        artist: str
        album: str

    def __init__(self):
        super().__init__()
        self.border_title = "Collection"

    def watch_collection(self, collection: list[CollectionEntry]) -> None:
        self.clear_options()

        for elem in collection:
            self.add_option(AlbumRow(elem.artist, elem.title))

        self.highlighted = 0
        self.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        album = self.collection[index]
        self.post_message(self.AlbumSelected(album.uid, album.artist, album.title))


class TrackList(JKOptionList):
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

        for i, track in enumerate(tracks):
            self.add_option(TrackRow(i, len(tracks), track.title, track.duration))
        self.highlighted = 0

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.post_message(self.TrackSelected(self.tracks, event.option_index))


class UpdateCollectionModal(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("Updating collection...")


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
        Binding("U", "update_collection", "Update collection"),
    ]

    def __init__(self) -> None:
        super().__init__()

        self._config = Config.load()
        self._api = SubsonicClient(
            username=self._config.username, password=self._config.password
        )
        self._collection = load_collection()
        self._mpv = mpv.MPV(
            force_seekable=True,
            prefetch_playlist=True,
        )

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Update collection", "Update collection", self.action_update_collection
        )

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield AlbumList()
            yield TrackList()

        yield ProgressBar(total=1.0, show_percentage=True, show_eta=False)
        yield Footer(compact=True)

    def on_mount(self) -> None:
        album_list = self.query_exactly_one(AlbumList)
        album_list.collection = self._collection
        self.progress_timer = self.set_interval(1.0, self.update_progress)

    def on_unmount(self) -> None:
        self._mpv.terminate()

    @work(exclusive=True)
    async def update_track_list(self, message: AlbumList.AlbumSelected) -> None:
        album_data = await self._api.get_album(message.uid)
        track_list = self.query_exactly_one(TrackList)
        track_list.border_title = f"{message.artist} - {message.album}"
        track_list.tracks = list(album_data.songs)

    async def on_album_list_album_selected(
        self, message: AlbumList.AlbumSelected
    ) -> None:
        self.update_track_list(message)

    def on_track_list_track_selected(self, message: TrackList.TrackSelected) -> None:
        self._mpv.stop(keep_playlist=False)
        self._mpv.playlist_clear()
        for track in message.tracks:
            url = self._api.get_stream_url(track.uid)
            self._mpv.playlist_append(str(url))
        self._mpv.playlist_pos = message.index

    def _set_playlist_pos(self, index: int) -> None:
        n = len(self._mpv.playlist_filenames)
        if n == 0:
            return
        self._mpv.playlist_pos = min(max(index, 0), n - 1)

    def action_prev(self) -> None:
        pos = self._mpv.playlist_pos
        if not isinstance(pos, int) or pos == -1:
            return
        self._set_playlist_pos(pos - 1)

    def action_next(self) -> None:
        pos = self._mpv.playlist_pos
        if not isinstance(pos, int) or pos == -1:
            return
        self._set_playlist_pos(pos + 1)

    def action_pause(self) -> None:
        self._mpv.pause = not self._mpv.pause

    def action_focus_collection(self) -> None:
        self.query_exactly_one(AlbumList).focus()

    def action_focus_track_list(self) -> None:
        self.query_exactly_one(TrackList).focus()

    def update_progress(self) -> None:
        percent_pos = self._mpv.percent_pos
        if percent_pos is None or not isinstance(percent_pos, float):
            return
        self.query_exactly_one(ProgressBar).update(progress=percent_pos / 100.0)

    async def action_update_collection(self) -> None:
        self.push_screen(UpdateCollectionModal())

        self._collection = await self._api.get_collection()
        save_collection(self._collection)

        self.pop_screen()

        album_list = self.query_exactly_one(AlbumList)
        album_list.collection = self._collection


if __name__ == "__main__":
    app = BCTUIApp()
    app.run()
