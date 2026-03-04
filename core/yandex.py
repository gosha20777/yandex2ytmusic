import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from yandex_music import Client
from yandex_music.exceptions import TimedOutError
from typing import List
from .track import Track
from tqdm import tqdm


class YandexMusicExporter:
    def __init__(self, token: str):
        self.client = Client(token).init()

    def _fetch_with_retry(self, track, max_retries=5, base_delay=2):
        for attempt in range(max_retries):
            try:
                return track.fetch_track()
            except TimedOutError:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    raise

    def _process_track(self, track) -> Track:
        """Process a single track and return Track object."""
        fetched = self._fetch_with_retry(track)
        
        # Если исполнители есть, объединяем весь список через запятую
        if fetched.artists_name():
            artist = ", ".join(fetched.artists_name())
        else:
            artist = "Unknown Artist"
            
        name = fetched.title
        return Track(artist, name)

    def export_liked_tracks(self, max_workers: int = 5) -> List[Track]:
        tracks = self.client.users_likes_tracks().tracks

        result = []
        with tqdm(total=len(tracks), desc='Export tracks') as pbar:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._process_track, track): i
                          for i, track in enumerate(tracks)}

                # Собираем результаты с сохранением порядка
                results_dict = {}
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        track_result = future.result()
                        results_dict[idx] = track_result
                        pbar.set_postfix_str(f'{track_result.artist} - {track_result.name}'[:40])
                    except Exception as e:
                        pbar.write(f'Error processing track: {e}')
                        results_dict[idx] = None
                    pbar.update(1)

                # Восстанавливаем порядок
                for i in range(len(tracks)):
                    if results_dict.get(i):
                        result.append(results_dict[i])

        return result
