bctui
=====

A simple text-based Bandcamp music player that allows you to stream your music collection.

bctui is built on the new (in beta) [OpenSubsonic API](https://blog.bandcamp.com/2026/07/16/discover-improvements-and-subsonic-implementation/) and uses libmpv for streaming and playback.
The TUI is implemented in Python using [Textual](https://textual.textualize.io).

![screenshot](https://github.com/user-attachments/assets/9d4825fa-56ae-4a8a-bbfc-10017303f2d5)

## Installation

First make sure `libmpv` is installed. On Debian-based systems you can install it with:
```sh
sudo apt install libmpv2
```

Then clone the repository and install the package, e.g.:

```sh
git clone https://github.com/SimonLarsen/bctui.git
cd bctui
uv run bctui
```

## Configuration

Create a new configuration file in `$XDG_CONFIG_HOME/bctui/bctui.json` and add your Bandcamp Subsonic username and password:

```sh
mkdir -p ~/.config/bctui
cat <<EOF> ~/.config/bctui/bctui.json
{
    "username": "XXXXXXXX",
    "password": "XXXXXXXX"
}
EOF
```

You can obtain your credentials under [Settings > Fan > Subsonic](https://bandcamp.com/settings?pane=fan#subsonic).
