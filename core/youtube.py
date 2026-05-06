import os
import json
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher

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
        self.search_ytmusic = YTMusic()

        if os.path.exists(token_path):
            with open(token_path, 'r') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON in {token_path}")

            if 'cookie' in data or 'Cookie' in data or 'x-origin' in data:
                self.auth_type = 'browser'
                self.ytmusic = YTMusic(self._sanitize_browser_headers(data))
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

    @staticmethod
    def _sanitize_browser_headers(headers: dict) -> dict:
        """
        Keep only headers supported by ytmusicapi browser auth.
        Some manually copied header dumps include pseudo/invalid keys that break requests.
        """
        allowed = {
            'accept',
            'accept-language',
            'authorization',
            'content-type',
            'cookie',
            'origin',
            'referer',
            'user-agent',
            'x-goog-authuser',
            'x-goog-visitor-id',
            'x-origin',
            'x-youtube-bootstrap-logged-in',
            'x-youtube-client-name',
            'x-youtube-client-version',
        }
        normalized = {}
        for key, value in headers.items():
            lowered = key.lower()
            if lowered in allowed:
                normalized[lowered] = value
        return normalized

    @staticmethod
    def _normalize_text(value: str) -> str:
        value = value.lower().strip()
        value = re.sub(r'\[[^\]]*\]|\([^)]*\)', ' ', value)
        value = re.sub(r'[\W_]+', ' ', value, flags=re.UNICODE)
        return re.sub(r'\s+', ' ', value).strip()

    def _build_queries(self, track: Track) -> List[str]:
        artist = track.artist.strip()
        name = track.name.strip()
        candidates = [f"{artist} {name}", f"{name} {artist}", name]
        uniq: List[str] = []
        seen = set()
        for q in candidates:
            key = q.lower()
            if key and key not in seen:
                seen.add(key)
                uniq.append(q)
        return uniq

    def _score_result(self, result: dict, track: Track) -> float:
        title = self._normalize_text(result.get('title', ''))
        target_title = self._normalize_text(track.name)
        title_score = SequenceMatcher(None, target_title, title).ratio()

        target_artist = self._normalize_text(track.artist)
        artists = result.get('artists') or []
        result_artists = " ".join(a.get('name', '') for a in artists if isinstance(a, dict))
        result_artists = self._normalize_text(result_artists)
        artist_score = SequenceMatcher(None, target_artist, result_artists).ratio() if result_artists else 0.0

        return (title_score * 0.75) + (artist_score * 0.25)

    def _search_candidates(self, query: str, search_filter: Optional[str]) -> List[dict]:
        last_error = None
        for attempt in range(3):
            try:
                return self.search_ytmusic.search(query, filter=search_filter)
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(1.0 * (attempt + 1))
        if last_error:
            raise last_error
        return []

    def _search_track(self, track: Track, idx: int) -> Tuple[int, Track, Optional[str], Optional[str]]:
        """
        Search for a track on YouTube Music.
        Returns (index, track, videoId or None, error or None).
        """
        best_result = None
        best_score = 0.0

        try:
            for query in self._build_queries(track):
                for search_filter in ('songs', 'videos', None):
                    results = self._search_candidates(query, search_filter)
                    if not results:
                        continue

                    for result in results:
                        if 'videoId' not in result:
                            continue
                        score = self._score_result(result, track)
                        if score > best_score:
                            best_score = score
                            best_result = result

                    if best_score >= 0.82:
                        break
                if best_score >= 0.82:
                    break
        except Exception as e:
            return (idx, track, None, str(e))

        if not best_result:
            return (idx, track, None, 'not_found')

        return (idx, track, best_result.get('videoId'), None)

    def _like_track(self, track: Track, video_id: str) -> Tuple[Track, bool, Optional[str]]:
        """Like a single track. Returns (track, success, error)."""
        try:
            self.ytmusic.rate_song(video_id, 'LIKE')
            return (track, True, None)
        except Exception as e:
            message = str(e)
            if '401' in message or 'Unauthorized' in message:
                message = '401 Unauthorized (истекла авторизация YouTube, запусти пункт 4 заново)'
            return (track, False, message)

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

            if error and error != 'not_found':
                errors.append(track)
            elif error == 'not_found' or not video_id:
                not_found.append(track)
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
                    except Exception as e:
                        errors.append(track)
                        pbar.write(f'Like error: {track.artist} - {track.name}: {e}')
                    pbar.update(1)
        else:
            # Параллельное добавление (быстрее, но порядок случайный)
            with tqdm(total=len(tracks_to_like), desc='Like') as pbar:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
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
                        except Exception as e:
                            errors.append(track)
                            pbar.write(f'Like error: {track.artist} - {track.name}: {e}')
                        pbar.update(1)

        return not_found, errors

    def _get_best_result(self, results: List[dict], track: Track) -> dict:
        songs = []
        for result in results:
            if 'videoId' not in result.keys():
                continue
            if result.get('category') == 'Top result':
                return result
            if result.get('title') == track.name:
                return result
            songs.append(result)
        if len(songs) == 0:
            return results[0]
        return songs[0]


# Алиас для обратной совместимости
YoutubeImoirter = YoutubeImporter
