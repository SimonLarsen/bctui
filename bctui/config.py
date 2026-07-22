from dataclasses import dataclass
import xdg.BaseDirectory
import json


class ConfigNotFoundError(Exception):
    pass


@dataclass
class Config:
    username: str
    password: str

    @classmethod
    def load(cls) -> "Config":
        path = xdg.BaseDirectory.load_first_config("bctui/bctui.json")
        if path is None:
            raise ConfigNotFoundError()

        with open(path, "r") as fp:
            js = json.load(fp)

        return cls(
            username=js["username"],
            password=js["password"],
        )
