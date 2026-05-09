import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from yandex_music import Client
from yandex_music.exceptions import TimedOutError
from typing import List
from .track import Track
from .playlist import Playlist
from .podcast import Podcast
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
        if fetched.artists_name():
            artist = fetched.artists_name()[0]
        else:
            artist = "Unknown Artist"
        name = fetched.title
        return Track(artist, name)
    
    def _process_podcast(self, podcast) -> Podcast:
        """Process a single podcast album and return Podcast object"""
        if podcast.labels:
            label = podcast.labels[0].name
        else:
            label = "Unknown Label"
        name = podcast.title
        return Podcast(label, name)
    
    def _process_playlist(self, playlist) -> Playlist:
        """Process a single playlist and return Playlist object."""
        fetched_tracks = playlist.fetch_tracks()
        # TODO: Parallel implementation? Not sure if order is important for some users...
        tracklist = [self._process_track(track) for track in fetched_tracks]
        return Playlist(playlist.title, playlist.description, tracklist)

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
    
    def export_liked_podcasts(self, max_workers: int = 5) -> List[Podcast]:
        # Подкасты в Яндекс Музыке записаны как альбомы с типом podcast
        podcasts = [album.album for album in self.client.users_likes_albums() if album.album.type == 'podcast']

        result = []
        with tqdm(total=len(podcasts), desc='Export podcasts') as pbar:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._process_podcast, podcast): i
                          for i, podcast in enumerate(podcasts)}

                # Собираем результаты с сохранением порядка
                results_dict = {}
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        podcast_result = future.result()
                        results_dict[idx] = podcast_result
                        pbar.set_postfix_str(f'{podcast_result.label} - {podcast_result.name}'[:40])
                    except Exception as e:
                        pbar.write(f'Error processing podcast: {e}')
                        results_dict[idx] = None
                    pbar.update(1)

                # Восстанавливаем порядок
                for i in range(len(podcasts)):
                    if results_dict.get(i):
                        result.append(results_dict[i])

        return result

    def export_playlists(self, max_workers: int = 5) -> List[Playlist]:
        playlists = [like.playlist for like in self.client.users_likes_playlists()]

        result = []
        with tqdm(total=len(playlists), desc='Export playlists') as pbar:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._process_playlist, playlist): i
                          for i, playlist in enumerate(playlists)}

                # Собираем результаты с сохранением порядка
                results_dict = {}
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        playlist_result = future.result()
                        results_dict[idx] = playlist_result
                        pbar.set_postfix_str(f'{playlist_result.title}'[:40])
                    except Exception as e:
                        pbar.write(f'Error processing playlist: {e}')
                        results_dict[idx] = None
                    pbar.update(1)

                # Восстанавливаем порядок
                for i in range(len(playlists)):
                    if results_dict.get(i):
                        result.append(results_dict[i])
        
        return result