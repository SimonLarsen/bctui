from typing import Any
import string
import random
import hashlib
import httpx
from bctui.types import CollectionEntry, AlbumData, TrackData


class SubsonicConnectionError(Exception):
    pass


class SubsonicCommandFailedError(Exception):
    pass


class SubsonicClient:
    def __init__(
        self,
        username: str,
        password: str,
        client_name: str = "bctui",
        url: str | httpx.URL = "https://bandcamp.com/api/subsonic",
        version: str = "1.16.1",
    ):
        self._username = username
        self._password = password
        self._client_name = client_name
        self._url = httpx.URL(url)
        self._version = version

    def _get_base_params(self) -> dict[str, str]:
        salt = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        token = hashlib.md5((self._password + salt).encode("utf-8")).hexdigest()
        params = dict(
            u=self._username,
            s=salt,
            t=token,
            c=self._client_name,
            v=self._version,
            f="json",
        )
        return params

    async def _get(
        self,
        endpoint: str,
        **kwargs,
    ) -> dict[str, Any]:
        params = self._get_base_params()
        params.update(kwargs)

        async with httpx.AsyncClient() as client:
            res = await client.get(
                url=self._url.copy_with(path=self._url.path + endpoint),
                params=params,
            )

            if res.status_code != 200:
                raise SubsonicConnectionError(
                    f"Received status code {res.status_code}."
                )

        data = res.json()
        if (
            "subsonic-response" not in data
            or data["subsonic-response"].get("status") != "ok"
        ):
            raise SubsonicCommandFailedError()

        return data

    async def get_collection(
        self,
        albums_per_query: int = 50,
    ) -> list[CollectionEntry]:
        albums: list[CollectionEntry] = []
        offset = 0
        while True:
            data = await self._get(
                "/rest/getAlbumList2",
                type="newest",
                size=albums_per_query,
                offset=offset,
            )
            new_albums = data["subsonic-response"]["albumList2"]["album"]
            if len(new_albums) == 0:
                break

            for e in new_albums:
                album = CollectionEntry(
                    uid=e["id"],
                    artist=e["artist"],
                    title=e["name"],
                    year=e.get("year"),
                    genre=e.get("genre"),
                )
                albums.append(album)

            offset += len(new_albums)

        return albums

    async def get_album(self, uid: str) -> AlbumData:
        data = await self._get("/rest/getAlbum", id=uid)
        info = data["subsonic-response"]["album"]

        songs: list[TrackData] = []
        for e in info["song"]:
            song = TrackData(
                uid=e["id"],
                artist=e["artist"],
                title=e["title"],
                duration=e["duration"],
                genre=e.get("genre"),
            )
            songs.append(song)

        return AlbumData(songs=songs)

    def get_stream_url(self, uid: str) -> httpx.URL:
        params = self._get_base_params()
        params.update(dict(id=uid, format="mp3"))
        url = self._url.copy_with(
            path=self._url.path + "/rest/stream",
            params=params,
        )
        return url
