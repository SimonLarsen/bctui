from dataclasses import dataclass

import mpv
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Label, OptionList, ProgressBar, Static

from bctui.cache import load_collection, save_collection
from bctui.config import Config
from bctui.format import duration_to_hhmmss
from bctui.renderables import AlbumRow, TrackRow
from bctui.subsonic import SubsonicClient
from bctui.types import CollectionEntry, TrackData


class JKOptionList(OptionList):
    BINDINGS = [
        Binding(key="j", action="cursor_down"),
        Binding(key="k", action="cursor_up"),
        Binding(key="space", action="select"),
        Binding(key="g", action="first"),
        Binding(key="G", action="last"),
    ]


class AlbumList(JKOptionList):
    collection: reactive[list[CollectionEntry]] = reactive([])
    playing_uid: reactive[str | None] = reactive(None)

    @dataclass
    class AlbumSelected(Message):
        album: CollectionEntry

    def __init__(self):
        super().__init__()
        self.border_title = "Collection"

    def _make_row(self, index: int) -> AlbumRow:
        album = self.collection[index]
        return AlbumRow(album.artist, album.title, album.uid == self.playing_uid)

    def watch_collection(self, collection: list[CollectionEntry]) -> None:
        self.clear_options()

        for i in range(len(self.collection)):
            self.add_option(self._make_row(i))

        self.highlighted = 0
        self.focus()

    def watch_playing_uid(self, old_uid: str | None, new_uid: str | None) -> None:
        for i, album in enumerate(self.collection):
            if album.uid == old_uid or album.uid == new_uid:
                self.replace_option_prompt_at_index(i, self._make_row(i))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        album = self.collection[index]
        self.post_message(self.AlbumSelected(album))


class TrackList(JKOptionList):
    album_uid: str | None = None
    tracks: reactive[list[TrackData]] = reactive([])
    playing_uid: reactive[str | None] = reactive(None)

    @dataclass
    class TrackSelected(Message):
        album_uid: str
        tracks: list[TrackData]
        index: int

    def __init__(self):
        super().__init__()
        self.border_title = "N/A - N/A"

    def _make_row(self, index: int) -> TrackRow:
        track = self.tracks[index]
        return TrackRow(
            index,
            len(self.tracks),
            track.title,
            track.duration,
            track.uid == self.playing_uid,
        )

    def watch_tracks(self, tracks: list[TrackData]) -> None:
        self.clear_options()

        for i in range(len(self.tracks)):
            self.add_option(self._make_row(i))

        self.highlighted = 0

    def watch_playing_uid(self, old_uid: str | None, new_uid: str | None) -> None:
        for i, track in enumerate(self.tracks):
            if track.uid == old_uid or track.uid == new_uid:
                self.replace_option_prompt_at_index(i, self._make_row(i))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if self.album_uid is None:
            return
        self.post_message(
            self.TrackSelected(self.album_uid, self.tracks, event.option_index)
        )


class UpdateCollectionModal(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("Updating collection...")


class StatusBar(Grid):
    title: reactive[str] = reactive("N/A", recompose=True)
    artist: reactive[str] = reactive("N/A", recompose=True)
    album: reactive[str] = reactive("N/A", recompose=True)
    position: reactive[float] = reactive(0.0, recompose=True)
    duration: reactive[float] = reactive(0.0, recompose=True)

    def compose(self) -> ComposeResult:
        yield Static(self.title, classes="statusbar--title")
        yield Static(" by ", classes="statusbar--separator")
        yield Static(self.artist, classes="statusbar--artist")
        yield Static(" from ", classes="statusbar--separator")
        yield Static(self.album, classes="statusbar--album")
        t1 = duration_to_hhmmss(self.position)
        t2 = duration_to_hhmmss(self.duration)
        yield Static(f"[{t1}/{t2}]", classes="statusbar--time")


class BCTUIApp(App):
    CSS_PATH = "style.tcss"

    AUTO_FOCUS = None

    BINDINGS = [
        Binding("F2", "search", "Search"),
        Binding("<", "prev", "Prev"),
        Binding(">", "next", "Next"),
        Binding("p", "pause", "Pause"),
        Binding("h", "focus_collection", "Focus collection", show=False),
        Binding("l", "focus_track_list", "Focus tracks", show=False),
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

        self._mpv.register_event_callback(self._handle_event)

        self._playlist: list[TrackData] = []

    def _handle_event(self, event: mpv.MpvEvent) -> None:
        if event.event_id.value == mpv.MpvEventID.START_FILE:
            self._update_track_list_playing()

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield AlbumList()
            yield TrackList()
        yield StatusBar()
        yield ProgressBar(
            total=1.0,
            show_percentage=False,
            show_eta=False,
        )
        yield Footer(compact=True)

    def on_mount(self) -> None:
        self.theme = self._config.theme

        self.progress_timer = self.set_interval(1.0, self.update_progress)

        album_list = self.query_exactly_one(AlbumList)
        album_list.collection = self._collection

    def on_unmount(self) -> None:
        self._mpv.terminate()

    def _update_track_list_playing(self) -> None:
        pos = self._mpv.playlist_pos
        if not isinstance(pos, int) or pos < 0:
            return

        track = self._playlist[pos]

        track_list = self.query_exactly_one(TrackList)
        track_list.playing_uid = track.uid

        status_bar = self.query_exactly_one(StatusBar)
        status_bar.artist = track.artist
        status_bar.title = track.title
        status_bar.album = track.album

    async def _update_track_list(self, message: AlbumList.AlbumSelected) -> None:
        album_data = await self._api.get_album(message.album.uid)
        track_list = self.query_exactly_one(TrackList)
        track_list.border_title = f"{message.album.artist} - {message.album.title}"
        track_list.album_uid = message.album.uid
        track_list.tracks = list(album_data.songs)
        self._update_track_list_playing()

    async def on_album_list_album_selected(
        self, message: AlbumList.AlbumSelected
    ) -> None:
        await self._update_track_list(message)
        self.query_exactly_one(TrackList).focus()

    def on_track_list_track_selected(self, message: TrackList.TrackSelected) -> None:
        self._mpv.stop(keep_playlist=False)
        self._mpv.playlist_clear()
        for track in message.tracks:
            url = self._api.get_stream_url(track.uid)
            self._mpv.playlist_append(str(url))
        self._set_playlist_pos(message.index)
        self.playing_album_uid = message.album_uid

        album_list = self.query_exactly_one(AlbumList)
        album_list.playing_uid = message.album_uid
        self._playlist = message.tracks

    def _set_playlist_pos(self, index: int) -> None:
        n = self._mpv.playlist_count
        if not isinstance(n, int) or n < 1:
            return
        self._mpv.playlist_pos = min(max(index, 0), n - 1)
        self._mpv.pause = False

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

    async def action_update_collection(self) -> None:
        self.push_screen(UpdateCollectionModal())

        self._collection = await self._api.get_collection()
        save_collection(self._collection)

        self.pop_screen()

        album_list = self.query_exactly_one(AlbumList)
        album_list.collection = self._collection

    def update_progress(self) -> None:
        percent_pos = self._mpv.percent_pos
        if isinstance(percent_pos, float):
            progress_bar = self.query_exactly_one(ProgressBar)
            progress_bar.update(progress=percent_pos / 100)

        status_bar = self.query_exactly_one(StatusBar)
        time_pos = self._mpv.time_pos
        if isinstance(time_pos, float):
            status_bar.position = time_pos

        duration = self._mpv.duration
        if isinstance(duration, float):
            status_bar.duration = duration


if __name__ == "__main__":
    app = BCTUIApp()
    app.run()
