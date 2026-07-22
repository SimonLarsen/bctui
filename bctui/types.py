from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class CollectionEntry:
    uid: str
    artist: str
    title: str
    year: int | None
    genre: str | None


@dataclass
class TrackData:
    uid: str
    artist: str
    title: str
    duration: int
    genre: str | None


@dataclass
class AlbumData:
    songs: Sequence[TrackData]
