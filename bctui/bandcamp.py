from dataclasses import dataclass
import json
import requests
from bs4 import BeautifulSoup


@dataclass
class Album:
    artist: str
    title: str
    url: str


def fetch_collection(
    collection_url: str,
    items_per_query: int = 20,
) -> list[Album]:
    """
    Fetch music collection from public fan page.

    Parameters
    ----------
    collection_url : str
        Fan page url e.g. 'https://bandcamp.com/simonlarsen'.

    Returns
    -------
    list[Album]
        List of albums.
    """
    res = requests.get(collection_url)

    if res.status_code != 200:
        raise RuntimeError("Could not fetch collection page.")

    soup = BeautifulSoup(res.content)
    data_div = soup.find("div", attrs={"id": "pagedata"})
    if data_div is None:
        raise RuntimeError("Collection page did not contains page data element.")

    if "data-blob" not in data_div.attrs:
        raise RuntimeError("pagedata element has not attribute 'data-blob'.")

    data = json.loads(str(data_div.attrs["data-blob"]))

    # Parse initial collection items
    albums = []
    for _, item in data["item_cache"]["collection"].items():
        album = Album(
            artist=item["band_name"],
            title=item["item_title"],
            url=item["item_url"],
        )
        albums.append(album)

    # Fetch remaining collection page iteratively
    # using API
    fan_id = int(data["fan_data"]["fan_id"])
    item_count = int(data["collection_data"]["item_count"])
    last_token = data["collection_data"]["last_token"]

    while True:
        res = requests.post(
            url="https://bandcamp.com/api/fancollection/1/collection_items",
            json=dict(
                count=items_per_query,
                fan_id=fan_id,
                older_than_token=last_token,
            )
        )
        if res.status_code != 200:
            raise RuntimeError("Error fetching collection from API.")

        data = res.json()
        for item in data["items"]:
            album = Album(
                artist=item["band_name"],
                title=item["item_title"],
                url=item["item_url"],
            )
            albums.append(album)

        if not data["more_available"]:
            break
        last_token = data["last_token"]

    return albums

