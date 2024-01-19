from yandex_music import Client, Artist
from typing import List
from .track import Track
from tqdm import tqdm


class YandexMusicExporter:
    def __init__(self, token: str):
        self.client = Client(token).init()

    def export_liked_tracks(self) -> List[Track]:
        tracks = self.client.users_likes_tracks().tracks

        result = []
        with tqdm(total=len(tracks), position=0, desc='Export tracks') as pbar:
            with tqdm(total=0, bar_format='{desc}', position=1) as trank_log:
                for track in tracks:
                    track = track.fetch_track()
                    artist = track.artists_name()[0]
                    name = track.title
                    result.append(Track(artist, name))
                    pbar.update(1)
                    trank_log.set_description_str(f'{artist} - {name}')
        return result
