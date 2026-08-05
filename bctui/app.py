from dataclasses import dataclass

import mpv
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Label, OptionList, ProgressBar

from bctui.cache import load_collection, save_collection
from bctui.config import Config
from bctui.renderables import AlbumRow, TrackRow
from bctui.subsonic import SubsonicClient
from bctui.types import CollectionEntry, TrackData
from bctui.widgets import StatusBar, VimOptionList


class AlbumList(VimOptionList):
    DEFAULT_CSS = """
    AlbumList {
        width: 0.5fr;
        height: 1fr;
        border: round $foreground;
        &:focus { border: round $primary; }
    }
    """
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


class TrackList(VimOptionList):
    DEFAULT_CSS = """
    TrackList {
        width: 0.5fr;
        height: 1fr;
        border: round $foreground;
        &:focus { border: round $primary; }
    }
    """
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
    DEFAULT_CSS = """
    UpdateCollectionModal {
        align: center middle;

        Vertical {
            border: round $foreground;
            width: 30;
            height: 4;
            padding: 0 1 0 1;

            Label {
                text-align: center;
            }
        }
    }
    """

    def __init__(self, api: SubsonicClient):
        super().__init__()
        self._api = api

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Updating collection...", expand=True)
            yield ProgressBar(show_bar=True, show_percentage=False, show_eta=False)

    async def on_show(self) -> None:
        collection = await self._api.get_collection()
        self.dismiss(collection)


class SearchModal(ModalScreen):
    DEFAULT_CSS = """
    SearchModal {
        align: center middle;

        Vertical {
            border: round $foreground;
            width: 80%;
            height: 80%;
        }
    }
    """

    def __init__(self, collection: list[CollectionEntry]):
        super().__init__()
        self._search_query: str = ""
        self._matched_indices: list[int] = []
        self._collection = collection

    def compose(self) -> ComposeResult:
        container = Vertical(
            Input(compact=True),
            VimOptionList(compact=True),
        )
        container.border_title = "Search"
        yield container

    def on_mount(self) -> None:
        self._update_list()
        self.query_exactly_one(Input).focus()

    def _update_list(self) -> None:
        options = []
        matched_indices = []
        for i, album in enumerate(self._collection):
            key = f"{album.artist.lower()} {album.title.lower()}"
            if self._search_query in key:
                options.append(AlbumRow(album.artist, album.title))
                matched_indices.append(i)

        search_list = self.query_exactly_one(VimOptionList)
        search_list.clear_options()
        search_list.add_options(options)
        self._matched_indices = matched_indices

        if len(options) > 0 and search_list.highlighted is None:
            search_list.highlighted = 0

    def _confirm(self) -> None:
        search_list = self.query_exactly_one(VimOptionList)
        index = search_list.highlighted
        if index is None:
            self.dismiss(None)
            return
        album = self._collection[self._matched_indices[index]]
        self.dismiss(album.uid)

    def _move_cursor(self, delta: int) -> None:
        search_list = self.query_exactly_one(VimOptionList)
        index = search_list.highlighted
        if index is None:
            return
        index += delta
        search_list.highlighted = index

    def on_input_changed(self, event: Input.Changed) -> None:
        self._search_query = event.value
        self._update_list()

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter":
            self._confirm()
            event.stop()
        elif event.key == "ctrl+p":
            self._move_cursor(-1)
        elif event.key == "ctrl+n":
            self._move_cursor(1)


class BCTUIApp(App):
    CSS_PATH = "style.tcss"

    ENABLE_COMMAND_PALETTE = False
    AUTO_FOCUS = None

    BINDINGS = [
        Binding("f2", "search", "Search"),
        Binding("<", "prev", "Prev"),
        Binding(">", "next", "Next"),
        Binding("p", "pause", "Pause"),
        Binding("h,left", "focus_collection", "Focus collection", show=False),
        Binding("l,right", "focus_track_list", "Focus tracks", show=False),
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

    @work
    async def action_search(self) -> None:
        uid = await self.push_screen_wait(SearchModal(self._collection))
        if uid is None:
            return

        album_list = self.query_exactly_one(AlbumList)
        for i, album in enumerate(self._collection):
            if album.uid == uid:
                album_list.highlighted = i
                album_list.action_select()
                return

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

    @work
    async def action_update_collection(self) -> None:
        self._collection = await self.push_screen_wait(UpdateCollectionModal(self._api))
        save_collection(self._collection)

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
