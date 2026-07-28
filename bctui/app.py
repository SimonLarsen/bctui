from dataclasses import dataclass

import mpv
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Label, OptionList, ProgressBar

from bctui.cache import load_collection, save_collection
from bctui.config import Config
from bctui.renderables import AlbumRow, TrackRow
from bctui.subsonic import SubsonicClient
from bctui.types import CollectionEntry, TrackData


class JKOptionList(OptionList):
    BINDINGS = [
        Binding(key="j", action="cursor_down"),
        Binding(key="k", action="cursor_up"),
        Binding(key="space", action="select"),
    ]


class AlbumList(JKOptionList):
    collection: reactive[list[CollectionEntry]] = reactive([])
    playing: reactive[int | None] = reactive(None)

    @dataclass
    class AlbumSelected(Message):
        album: CollectionEntry

    def __init__(self):
        super().__init__()
        self.border_title = "Collection"

    def _make_row(self, index: int) -> AlbumRow:
        album = self.collection[index]
        return AlbumRow(album.artist, album.title, index == self.playing)

    def watch_collection(self, collection: list[CollectionEntry]) -> None:
        self.clear_options()

        for i in range(len(self.collection)):
            self.add_option(self._make_row(i))

        self.highlighted = 0
        self.focus()

    def watch_playing(self, old_playing: int | None, new_playing: int | None) -> None:
        if old_playing is not None:
            self.replace_option_prompt_at_index(
                old_playing, self._make_row(old_playing)
            )

        if new_playing is not None:
            self.replace_option_prompt_at_index(
                new_playing, self._make_row(new_playing)
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        album = self.collection[index]
        self.post_message(self.AlbumSelected(album))


class TrackList(JKOptionList):
    album_uid: str | None = None
    tracks: reactive[list[TrackData]] = reactive([])
    playing: reactive[int | None] = reactive(None)

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
            index, len(self.tracks), track.title, track.duration, index == self.playing
        )

    def watch_tracks(self, tracks: list[TrackData]) -> None:
        self.clear_options()

        for i in range(len(self.tracks)):
            self.add_option(self._make_row(i))

        self.highlighted = 0

    def watch_playing(self, old_playing: int | None, new_playing: int | None) -> None:
        if old_playing is not None:
            self.replace_option_prompt_at_index(
                old_playing, self._make_row(old_playing)
            )

        if new_playing is not None:
            self.replace_option_prompt_at_index(
                new_playing, self._make_row(new_playing)
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if self.album_uid is None:
            return
        self.post_message(
            self.TrackSelected(self.album_uid, self.tracks, event.option_index)
        )


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

    playing_album_uid: str | None = None

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

    def _handle_event(self, event: mpv.MpvEvent) -> None:
        if event.event_id.value == mpv.MpvEventID.START_FILE:
            self._update_track_list_playing()

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

    def _update_track_list_playing(self) -> None:
        track_list = self.query_exactly_one(TrackList)
        pos = self._mpv.playlist_pos
        if (
            not isinstance(pos, int)
            or pos == -1
            or track_list.album_uid != self.playing_album_uid
        ):
            pos = None
        track_list.playing = pos

    async def _update_track_list(self, message: AlbumList.AlbumSelected) -> None:
        album_data = await self._api.get_album(message.album.uid)
        track_list = self.query_exactly_one(TrackList)
        track_list.border_title = f"{message.album.artist} - {message.album.title}"
        track_list.playing = None
        track_list.tracks = list(album_data.songs)
        track_list.album_uid = message.album.uid
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
        for i, album in enumerate(self._collection):
            if album.uid == message.album_uid:
                album_list.playing = i
                break

    def _set_playlist_pos(self, index: int) -> None:
        n = len(self._mpv.playlist_filenames)
        if n == 0:
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
        if percent_pos is None or not isinstance(percent_pos, float):
            return
        self.query_exactly_one(ProgressBar).update(progress=percent_pos / 100.0)


if __name__ == "__main__":
    app = BCTUIApp()
    app.run()
