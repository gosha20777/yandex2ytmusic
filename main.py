import os
import sys
import json

if getattr(sys, 'frozen', False):
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'

from core import YandexMusicExporter
from core import YoutubeImoirter
from core.track import Track


def export_from_yandex(out_path: str) -> None:
    """Export tracks from Yandex Music to JSON file."""
    token = input("Введи токен Yandex Music: ").strip()
    if not token:
        print("Ошибка: токен не указан")
        return

    importer = YandexMusicExporter(token)

    print('Экспорт лайкнутых треков из Яндекс Музыки...')
    tracks = importer.export_liked_tracks()
    tracks.reverse()

    data = {
        'liked_tracks': [{'artist': t.artist, 'name': t.name} for t in tracks],
        'not_found': [],
        'errors': [],
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'Экспортировано {len(tracks)} треков в {out_path}')


def import_to_youtube(in_path: str, youtube_creds: str) -> None:
    """Import tracks from JSON file to YouTube Music."""
    if not os.path.exists(in_path):
        print(f"Ошибка: файл {in_path} не найден. Сначала выполни экспорт из Яндекс Музыки.")
        return

    if not os.path.exists(youtube_creds):
        print(f"Ошибка: файл {youtube_creds} не найден. Сначала настрой авторизацию YouTube.")
        return

    with open(in_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tracks = [Track(artist=t['artist'], name=t['name']) for t in data['liked_tracks']]
    print(f'Загружено {len(tracks)} треков из {in_path}')

    # Выбор режима импорта
    print("\nРежим импорта:")
    print("  ВНИМАНИЕ: При параллельном импорте более 100 треков YouTube может не сохранить часть лайков!")
    print("  1. Быстрый (параллельный, порядок не сохраняется)")
    print("  2. С сохранением порядка (медленнее)")
    mode_choice = input("\nВыбор (1-2): ").strip()

    keep_order = mode_choice != "1"

    exporter = YoutubeImoirter(youtube_creds)

    print('Импорт треков в YouTube Music...')
    not_found, errors = exporter.import_liked_tracks(tracks, keep_order=keep_order)

    data['not_found'] = [{'artist': t.artist, 'name': t.name} for t in not_found]
    data['errors'] = [{'artist': t.artist, 'name': t.name} for t in errors]

    for track in not_found:
        print(f'Не найдено: {track.artist} - {track.name}')

    print(f'{len(not_found)} не найдено, {len(errors)} ошибок.')

    with open(in_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def setup_youtube_auth(creds_path: str) -> None:
    """Setup YouTube Music authentication."""
    print("\nВыбери способ авторизации YouTube Music:")
    print("  1. Автоматически через браузер (могут быть ошибки авторизации)")
    print("  2. Вручную (вставить headers) <-- рекомендуется")

    choice = input("\nВыбор (1-2): ").strip()

    if choice == "1":
        auto_browser_auth(creds_path)
    elif choice == "2":
        manual_browser_auth(creds_path)
    else:
        print("Неверный выбор")


def auto_browser_auth(creds_path: str) -> None:
    """Automatically extract headers from browser using Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Ошибка: Playwright не установлен.")
        return

    print("\nОткрою браузер для авторизации...")
    print("1. Войди в аккаунт Google (если не залогинен)")
    print("2. Дождись загрузки YouTube Music")
    print("3. Браузер закроется автоматически\n")

    captured_headers = {}

    def capture_request(request):
        nonlocal captured_headers
        if "music.youtube.com/youtubei/v1/browse" in request.url and request.method == "POST":
            headers = dict(request.headers)
            if "cookie" in headers and "authorization" in headers:
                captured_headers = headers

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            page.on("request", capture_request)

            page.goto("https://music.youtube.com")

            # Ждём пока пользователь залогинится и headers будут перехвачены
            print("Ожидание авторизации (максимум 2 минуты)...")
            for _ in range(120):  
                page.wait_for_timeout(1000)
                if captured_headers:
                    break

            browser.close()

        if not captured_headers:
            print("Не удалось перехватить headers. Попробуй ручной способ.")
            return

        # Сохраняем только нужные headers
        headers_to_save = {
            "accept": captured_headers.get("accept", "*/*"),
            "accept-encoding": captured_headers.get("accept-encoding", "gzip, deflate"),
            "accept-language": captured_headers.get("accept-language", "en-US,en;q=0.9"),
            "authorization": captured_headers.get("authorization", ""),
            "content-type": captured_headers.get("content-type", "application/json"),
            "cookie": captured_headers.get("cookie", ""),
            "origin": "https://music.youtube.com",
            "referer": "https://music.youtube.com/",
            "user-agent": captured_headers.get("user-agent", ""),
            "x-goog-authuser": captured_headers.get("x-goog-authuser", "0"),
            "x-goog-visitor-id": captured_headers.get("x-goog-visitor-id", ""),
            "x-origin": "https://music.youtube.com",
            "x-youtube-bootstrap-logged-in": captured_headers.get("x-youtube-bootstrap-logged-in", "true"),
            "x-youtube-client-name": captured_headers.get("x-youtube-client-name", "67"),
            "x-youtube-client-version": captured_headers.get("x-youtube-client-version", ""),
        }

        with open(creds_path, 'w') as f:
            json.dump(headers_to_save, f, indent=4)

        print(f"\nАвторизация сохранена в {creds_path}")

    except Exception as e:
        print(f"Ошибка запуска браузера: {e}")
        print("\nПопробуй ручной способ (вариант 2)")


def manual_browser_auth(creds_path: str) -> None:
    """Manual browser authentication setup."""
    from ytmusicapi import setup

    print("\n=== Ручная авторизация ===")
    print("1. Открой https://music.youtube.com в браузере (войди в аккаунт)")
    print("2. Открой DevTools (F12)")
    print("3. Вкладка Network, фильтр по 'browse'")
    print("4. Кликни на любой POST запрос к browse?...")
    print("5. Скопируй ВСЕ Request Headers")
    print("\nВставь заголовки и нажми Ctrl+D (или Ctrl+Z в Windows):\n")

    setup(filepath=creds_path)

    if os.path.exists(creds_path):
        print(f"\nАвторизация сохранена в {creds_path}")
    else:
        print("\nОшибка: файл не создан")


def full_transfer(tracks_path: str, youtube_creds: str) -> None:
    """Full transfer: export from Yandex and import to YouTube."""
    export_from_yandex(tracks_path)

    if not os.path.exists(tracks_path):
        return

    if not os.path.exists(youtube_creds):
        print("\nТеперь настроим авторизацию YouTube Music...")
        setup_youtube_auth(youtube_creds)

    if os.path.exists(youtube_creds):
        import_to_youtube(tracks_path, youtube_creds)


def main() -> None:
    tracks_path = "tracks.json"
    youtube_creds = "browser.json"

    while True:
        print("\n=== Yandex Music → YouTube Music ===")
        print("Что хочешь сделать?")
        print("  1. Полный перенос (экспорт из Яндекса + импорт в YouTube)")
        print("  2. Только экспорт из Яндекс Музыки")
        print("  3. Только импорт в YouTube Music (из файла)")
        print("  4. Настроить авторизацию YouTube Music")
        print("  0. Выйти из программы")

        choice = input("\nВыбор (0-4): ").strip()

        match choice:
            case "1":
                full_transfer(tracks_path, youtube_creds)
            case "2":
                export_from_yandex(tracks_path)
            case "3":
                import_to_youtube(tracks_path, youtube_creds)
            case "4":
                setup_youtube_auth(youtube_creds)
            case "0":
                print("Завершение работы...")
                break
            case _:
                print("Неверный выбор. Введите число от 0 до 4.")


if __name__ == '__main__':
    main()