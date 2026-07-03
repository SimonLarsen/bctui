from collections.abc import Sequence
from dataclasses import dataclass
import json
import requests
from bs4 import BeautifulSoup


@dataclass
class CollectionEntry:
    uid: int
    artist: str
    title: str
    url: str


@dataclass
class TrackData:
    uid: int
    artist: str | None
    title: str
    url: str
    duration: float


@dataclass
class AlbumData:
    tracks: Sequence[TrackData]


def fetch_collection(
    collection_url: str,
    items_per_query: int = 20,
) -> list[CollectionEntry]:
    """
    Fetch music collection from public fan page.

    Parameters
    ----------
    collection_url : str
        Fan page url e.g. 'https://bandcamp.com/simonlarsen'.

    Returns
    -------
    list[CollectionEntry]
        List of albums/tracks in collection.
    """
    res = requests.get(collection_url)

    if res.status_code != 200:
        raise RuntimeError("Could not fetch collection page.")

    soup = BeautifulSoup(res.content, "html.parser")
    data_div = soup.find("div", attrs={"id": "pagedata"})
    if data_div is None:
        raise RuntimeError("Collection page did not contains page data element.")

    if "data-blob" not in data_div.attrs:
        raise RuntimeError("pagedata element has not attribute 'data-blob'.")

    data = json.loads(str(data_div.attrs["data-blob"]))

    # Parse initial collection items
    collection = []
    for _, item in data["item_cache"]["collection"].items():
        entry = CollectionEntry(
            uid=item["item_id"],
            artist=item["band_name"],
            title=item["item_title"],
            url=item["item_url"],
        )
        collection.append(entry)

    # Fetch remaining collection page iteratively
    # using API
    fan_id = int(data["fan_data"]["fan_id"])
    last_token = data["collection_data"]["last_token"]

    while True:
        res = requests.post(
            url="https://bandcamp.com/api/fancollection/1/collection_items",
            json=dict(
                count=items_per_query,
                fan_id=fan_id,
                older_than_token=last_token,
            ),
        )
        if res.status_code != 200:
            raise RuntimeError("Error fetching collection from API.")

        data = res.json()
        for item in data["items"]:
            entry = CollectionEntry(
                uid=item["item_id"],
                artist=item["band_name"],
                title=item["item_title"],
                url=item["item_url"],
            )
            collection.append(entry)

        if not data["more_available"]:
            break
        last_token = data["last_token"]

    return collection


def fetch_album(album_url: str) -> AlbumData:
    """
    Fetch album data from album page.

    Parameters
    ----------
    album_url : str
        Album (or track) page url e.g. 'https://meisemones.bandcamp.com/album/tsukino'.

    Returns
    -------
    AlbumData
        Album data.
    """
    res = requests.get(album_url)
    if res.status_code != 200:
        raise RuntimeError("Could not fetch album page.")

    soup = BeautifulSoup(res.content)
    data = None
    for script in soup.find_all("script"):
        if "data-tralbum" in script.attrs:
            data = json.loads(str(script.attrs["data-tralbum"]))

    if data is None:
        raise RuntimeError("Page did not contain any album data.")

    tracks = []
    for item in data["trackinfo"]:
        track = TrackData(
            uid=item["track_id"],
            artist=str(item["artist"]) if item["artist"] is not None else None,
            title=item["title"],
            url=str(item["file"]["mp3-128"]),
            duration=float(item["duration"]),
        )
        tracks.append(track)

    return AlbumData(tracks=tracks)
