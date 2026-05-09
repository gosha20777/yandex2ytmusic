import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm
from ytmusicapi import YTMusic, setup_oauth
from typing import List, Tuple, Optional
from .track import Track
from .podcast import Podcast
from .playlist import Playlist


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
    
    def _search_podcast(self, podcast: Podcast, idx: int) -> Tuple[int, Podcast, Optional[str], Optional[str]]:
        """
        Search for a podcast on YouTube Music.
        Returns (index, podcast, browseId or None, error or None).
        """
        query = f'{podcast.name}'

        try:
            results = self.ytmusic.search(query)
        except Exception as e:
            return (idx, podcast, None, str(e))

        # Since we search by the exact name of the podcast,
        # we expect it to be the first result, and consider
        # the search failed if it's not
        search_result = results[0]

        if search_result.get('resultType') != 'podcast':
            return (idx, podcast, None, 'not_found')

        browse_id = search_result.get('browseId')
        playlist_id = browse_id.replace('MPSP', '', 1) # We need to remove the prefix for podcasts
        return (idx, podcast, playlist_id, None)

    def _like_track(self, track: Track, video_id: str) -> Tuple[Track, bool, Optional[str]]:
        """Like a single track. Returns (track, success, error)."""
        try:
            self.ytmusic.rate_song(video_id, 'LIKE')
            return (track, True, None)
        except Exception as e:
            return (track, False, str(e))
        
    def _like_podcast(self, podcast: Podcast, playlist_id: str) -> Tuple[Podcast, bool, Optional[str]]:
        """Like a single podcast. Returns (podcast, success, error)."""
        try:
            self.ytmusic.rate_playlist(playlist_id, 'LIKE')
            return (podcast, True, None)
        except Exception as e:
            return (podcast, False, str(e))

    def _create_playlist(self, playlist: Playlist, max_workers: int = 5) -> Tuple[List[Track], List[Track]]:
        """
        Creates a playlist.

        Args:
            playlist: Playlist to create
            max_workers: Number of parallel workers (default 5). Used for track search only
        
        Returns:
            Tuple[List[Track], List[Track]]: A list of not found tracks and a list of tracks that encountered during search
        """
        not_found = []
        errors = []
        # Этап 1: Параллельный поиск
        search_results = {}  # idx -> (track, videoId, error)
        tracks = playlist.tracks
        with tqdm(total=len(tracks), desc='Search for tracks in playlist') as pbar:
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

        # Собираем треки для плейлиста
        tracks_to_add = []  # (idx, track, video_id)
        for idx in range(len(tracks)):
            track, video_id, error = search_results[idx]

            if error == 'not_found' or not video_id:
                not_found.append(track)
            elif error:
                errors.append(track)
            else:
                tracks_to_add.append(video_id)
        
        self.ytmusic.create_playlist(playlist.title, playlist.description, video_ids=tracks_to_add)
        
        return (not_found, errors)

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
    
    def import_liked_podcasts(self, podcasts: List[Podcast], max_workers: int = 5, keep_order: bool = True) -> Tuple[List[Podcast], List[Podcast]]:
        """
        Import podcasts to YouTube Music.

        Args:
            podcasts: List of podcasts to import
            max_workers: Number of parallel workers (default 5)
            keep_order: If True, likes are added sequentially to preserve order (slower).
                       If False, likes are added in parallel (faster, random order).
        """
        not_found: List[Podcast] = []
        errors: List[Podcast] = []

        # Этап 1: Параллельный поиск
        search_results = {}  # idx -> (podcast, videoId, error)

        print("Поиск подкастов...")
        with tqdm(total=len(podcasts), desc='Search') as pbar:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._search_podcast, podcast, idx): idx
                          for idx, podcast in enumerate(podcasts)}

                for future in as_completed(futures):
                    try:
                        idx, podcast, playlist_id, error = future.result()
                        search_results[idx] = (podcast, playlist_id, error)
                        pbar.set_postfix_str(f'{podcast.label} - {podcast.name}'[:40])
                    except Exception as e:
                        idx = futures[future]
                        search_results[idx] = (podcast[idx], None, str(e))
                    pbar.update(1)

        # Собираем подкасты для лайков
        podcasts_to_like = []  # (idx, podcast, playlist_id)
        for idx in range(len(podcasts)):
            podcast, playlist_id, error = search_results[idx]

            if error == 'not_found' or not playlist_id:
                not_found.append(podcast)
            elif error:
                errors.append(podcast)
            else:
                podcasts_to_like.append((idx, podcast, playlist_id))

        # Этап 2: Добавление лайков
        print("Добавление лайков...")

        if keep_order:
            # Последовательное добавление для сохранения порядка
            with tqdm(total=len(podcasts_to_like), desc='Like') as pbar:
                for idx, podcast, playlist_id in podcasts_to_like:
                    try:
                        self.ytmusic.rate_playlist(playlist_id, 'LIKE')
                        pbar.set_postfix_str(f'{podcast.label} - {podcast.name}'[:40])
                    except Exception as e:
                        errors.append(podcast)
                        pbar.write(f'Like error: {podcast.label} - {podcast.name}: {e}')
                    pbar.update(1)
        else:
            # Параллельное добавление (быстрее, но порядок случайный)
            with tqdm(total=len(podcasts_to_like), desc='Like') as pbar:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(self._like_podcast, podcast, playlist_id): podcast
                              for idx, podcast, playlist_id in podcasts_to_like}

                    for future in as_completed(futures):
                        podcast = futures[future]
                        try:
                            _, success, error = future.result()
                            if not success:
                                errors.append(podcast)
                                pbar.write(f'Like error: {podcast.label} - {podcast.name}: {error}')
                            pbar.set_postfix_str(f'{podcast.label} - {podcast.name}'[:40])
                        except Exception as e:
                            errors.append(podcast)
                            pbar.write(f'Like error: {podcast.label} - {podcast.name}: {e}')
                        pbar.update(1)

        return not_found, errors

    def import_playlists(self, playlists: List[Playlist], max_workers: int = 5) -> List[Playlist]:
        """
        Import playlists to YouTube Music.

        Args:
            playlists: List of playlists to import
            max_workers: Number of parallel workers (default 5). Used for track search only

        Returns:
            List[Playlist]: A list of Playlists that encountered errors during creation
        """
        errors: List[Playlist] = []

        # Последовательное создание плейлистов
        # TODO: Подумать над параллелизацией
        with tqdm(total=len(playlists), desc='Playlist creation') as pbar:
            for playlist in playlists:
                try:
                    not_found, errors = self._create_playlist(playlist, max_workers=max_workers)
                    if not_found or errors:
                        print(f'Плейлист: {playlist.title}')
                        for track in not_found:
                            print(f'Не найдено: {track.artist} - {track.name}')
                        for track in errors:
                            print(f'Ошибка при поиске: {track.artist} - {track.name}')
                    pbar.set_postfix_str(f'{playlist.title}'[:40])
                except Exception as e:
                    errors.append(playlist)
                    pbar.write(f'Playlist creation error: {playlist.title}: {e}')
                pbar.update(1)
        return errors

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
