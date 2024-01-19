from ytmusicapi import YTMusic, setup_oauth
from .track import Track
from typing import List, Tuple
import os
from tqdm import tqdm


class YoutubeImoirter:
    def __init__(self, token_path: str):
        if not os.path.exists(token_path):
            token = setup_oauth().as_json()
            with open(token_path, 'w') as f:
                f.write(token)
        else:
            token = open(token_path, 'r').read()

        self.ytmusic = YTMusic(token)

    def import_liked_tracks(self, tracks: List[Track]) -> Tuple[List[Track], List[Track]]:
        not_found = []
        errors = []
        with tqdm(total=len(tracks), position=0, desc='Import tracks') as pbar:
            with tqdm(total=0, bar_format='{desc}', position=1) as trank_log:
                for track in tracks:
                    results = self.ytmusic.search(f'{track.artist} {track.name}')
                    if len(results) == 0:
                        not_found.append(track)
                        continue
                    
                    result = self._get_best_result(results, track)
                    try:
                        self.ytmusic.rate_song(result['videoId'], 'LIKE')
                    except Exception as e:
                        errors.append(track)
                        pbar.write(f'Error: {track.artist} - {track.name}, {e}')
                    pbar.update(1)
                    trank_log.set_description_str(f'{track.artist} - {track.name}')

                return not_found, errors
    
    def _get_best_result(self, results: List[dict], track: Track) -> dict:
        songs = []
        for result in results:
            if 'videoId' not in result.keys():
                continue
            if result['category'] == 'Top result':
                return result
            if result['title'] == track.name:
                return result
            songs.append(result)
        if len(songs) == 0:
            return results[0]
        return songs[0]
        