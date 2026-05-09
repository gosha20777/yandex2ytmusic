from typing import NamedTuple, List
from .track import Track

class Playlist(NamedTuple):
    title: str
    description: str
    tracks: List[Track]

Playlist('test', 'test desc', [Track('big bob', 'noname')])