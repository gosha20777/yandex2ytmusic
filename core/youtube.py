import os
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm
from ytmusicapi import YTMusic, setup_oauth
from typing import List, Tuple, Optional
from .track import Track


class YoutubeImporter:
    def __init__(self, token_path: str, client_secrets_path: str = None):
        """
        Initialize YouTube Music importer.

        Args:
            token_path: Path to credentials file (OAuth JSON or browser headers JSON)
            client_secrets_path: Path to Google OAuth client secrets (optional, for OAuth auth)
        """
        self.token_path = token_path
        self.client_secrets_path = client_secrets_path

        if os.path.exists(token_path):
            with open(token_path, 'r') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON in {token_path}")

            if 'cookie' in data or 'Cookie' in data or 'x-origin' in data:
                self.auth_type = 'browser'
                self.ytmusic = YTMusic(token_path)
            else:
                self.auth_type = 'oauth'
                if not client_secrets_path or not os.path.exists(client_secrets_path):
                    raise FileNotFoundError(
                        "OAuth token found but client secrets file required. "
                        "Use --client-secrets or switch to browser authentication."
                    )
                self._init_oauth(token_path, client_secrets_path)
        else:
            if client_secrets_path and os.path.exists(client_secrets_path):
                self.auth_type = 'oauth'
                self._init_oauth(token_path, client_secrets_path)
            else:
                raise FileNotFoundError(
                    f"Credentials file not found: {token_path}\n"
                    "Either:\n"
                    "  1. Create browser auth: ytmusicapi browser --file browser.json\n"
                    "  2. Use OAuth with --client-secrets option"
                )

    def _init_oauth(self, token_path: str, client_secrets_path: str):
        """Initialize OAuth authentication."""
        from ytmusicapi.auth.oauth import OAuthCredentials

        with open(client_secrets_path, 'r') as f:
            secrets = json.load(f)['installed']

        self.oauth_credentials = OAuthCredentials(secrets['client_id'], secrets['client_secret'])

        if not os.path.exists(token_path):
            token = setup_oauth(secrets['client_id'], secrets['client_secret']).as_json()
            with open(token_path, 'w') as f:
                f.write(token)

        self.ytmusic = YTMusic(token_path, oauth_credentials=self.oauth_credentials)

    def _search_track(self, track: Track, idx: int) -> Tuple[int, Track, Optional[str], Optional[str]]:
        """
        Search for a track on YouTube Music.
        Returns (index, track, videoId or None, error or None).
        """
        query = f'{track.artist} {track.name}'

        try:
            results = self.ytmusic.search(query, filter='songs')
        except Exception as e:
            return (idx, track, None, str(e))

        if not results:
            return (idx, track, None, 'not_found')

        result = self._get_best_result(results, track)
        return (idx, track, result.get('videoId'), None)

    def _like_track(self, track: Track, video_id: str) -> Tuple[Track, bool, Optional[str]]:
        """Like a single track. Returns (track, success, error)."""
        try:
            self.ytmusic.rate_song(video_id, 'LIKE')
            return (track, True, None)
        except Exception as e:
            return (track, False, str(e))

    def import_liked_tracks(self, tracks: List[Track], max_workers: int = 5, keep_order: bool = True) -> Tuple[List[Track], List[Track]]:
        """
        Import tracks to YouTube Music.

        Args:
            tracks: List of tracks to import
            max_workers: Number of parallel workers (default 5)
            keep_order: If True, likes are added sequentially to preserve order (slower).
                       If False, likes are added in parallel (faster, random order).
        """
        not_found: List[Track] = []
        errors: List[Track] = []

        # Этап 1: Параллельный поиск
        search_results = {}  # idx -> (track, videoId, error)

        print("Поиск треков...")

        with tqdm(total=len(tracks), desc='Search') as pbar:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._search_track, track, idx): idx
                          for idx, track in enumerate(tracks)}

                for future in as_completed(futures):
                    try:
                        idx, track, video_id, error = future.result()
                        search_results[idx] = (track, video_id, error)
                        pbar.set_postfix_str(f'{track.artist} - {track.name}'[:40])
                    except Exception as e:
                        idx = futures[future]
                        search_results[idx] = (tracks[idx], None, str(e))
                    pbar.update(1)

        # Собираем треки для лайков
        tracks_to_like = []  # (idx, track, video_id)
        for idx in range(len(tracks)):
            track, video_id, error = search_results[idx]

            if error == 'not_found' or not video_id:
                not_found.append(track)
            elif error:
                errors.append(track)
            else:
                tracks_to_like.append((idx, track, video_id))

        # Этап 2: Добавление лайков
        print("Добавление лайков...")

        if keep_order:
            # Последовательное добавление для сохранения порядка
            with tqdm(total=len(tracks_to_like), desc='Like') as pbar:
                for idx, track, video_id in tracks_to_like:
                    try:
                        self.ytmusic.rate_song(video_id, 'LIKE')
                        pbar.set_postfix_str(f'{track.artist} - {track.name}'[:40])
                        time.sleep(random.uniform(1.0, 2.0))
                    except Exception as e:
                        errors.append(track)
                        pbar.write(f'Like error: {track.artist} - {track.name}: {e}')
                        time.sleep(5) 
                    pbar.update(1)
        else:
            # Параллельное добавление (быстрее, но порядок случайный)
            print("ВНИМАНИЕ: При параллельном импорте более 100 треков YouTube может не сохранить часть лайков!")
            with tqdm(total=len(tracks_to_like), desc='Like') as pbar:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = {executor.submit(self._like_track, track, video_id): track
                              for idx, track, video_id in tracks_to_like}

                    for future in as_completed(futures):
                        track = futures[future]
                        try:
                            _, success, error = future.result()
                            if not success:
                                errors.append(track)
                                pbar.write(f'Like error: {track.artist} - {track.name}: {error}')
                            pbar.set_postfix_str(f'{track.artist} - {track.name}'[:40])
                            time.sleep(1.5)
                        except Exception as e:
                            errors.append(track)
                            pbar.write(f'Like error: {track.artist} - {track.name}: {e}')
                        pbar.update(1)

        return not_found, errors

    def _get_best_result(self, results: List[dict], track: Track) -> dict:
        # Приводим оригинальное название к нижнему регистру и убираем пробелы по краям
        ya_title = track.name.lower().strip()
        
        # Разбиваем строку исполнителей ("Артист 1, Артист 2") в список
        ya_artists = [a.strip().lower() for a in track.artist.split(',')]

        # Оставляем только те результаты, у которых есть videoId (исключаем пустые карточки)
        valid_songs = [r for r in results if r.get('videoId')]
        
        if not valid_songs:
            # Если почему-то нет треков с videoId, возвращаем первый попавшийся элемент (или пустой словарь)
            return results[0] if results else {}

        best_partial_match = None

        for result in valid_songs:
            yt_title = result.get('title', '').lower().strip()
            
            # Получаем список исполнителей из ответа YouTube Music
            yt_artists_list = result.get('artists', [])
            yt_artists = [a.get('name', '').lower().strip() for a in yt_artists_list]

            # Проверяем, совпадает ли хотя бы один исполнитель
            artist_match = False
            for ya_artist in ya_artists:
                for yt_artist in yt_artists:
                    # Проверяем вхождение
                    if ya_artist in yt_artist or yt_artist in ya_artist:
                        artist_match = True
                        break
                if artist_match:
                    break
            
            # УСЛОВИЕ 1: Идеальное совпадение
            if ya_title == yt_title and artist_match:
                return result
            
            # УСЛОВИЕ 2: Частичное совпадение названия
            if best_partial_match is None and artist_match and (ya_title in yt_title or yt_title in ya_title):
                best_partial_match = result

        # Если нашли частичное совпадение
        if best_partial_match:
            return best_partial_match

        # Точных совпадений по тексту нет
        # В таком случае просто доверяемся поисковику YouTube и берем самый первый трек из выдачи.
        return valid_songs[0]


# Алиас для обратной совместимости
YoutubeImoirter = YoutubeImporter
