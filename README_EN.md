# yandex2ytmusic

**[Русский язык](README.md)**

Transfer liked tracks, playlists and podcasts from Yandex.Music to YouTube Music.

**Fork of [gosha20777/yandex2ytmusic](https://github.com/gosha20777/yandex2ytmusic) with improvements.**

## What's New

| Feature | Original | This Version |
|---------|----------|--------------|
| Interactive menu | No (CLI flags only) | Yes |
| Separate export/import | No | Yes |
| Automatic YouTube auth | No | Yes (via Playwright) |
| Browser authentication | No | Yes |
| Multithreading | No | Yes (up to 5x faster) |
| Import mode selection | No | Fast / Preserve order |
| Progress saving between steps | No | Yes |

### Key Improvements

- **Interactive menu** — no need to remember command-line flags
- **Separate export/import** — export tracks, playlists and podcasts from Yandex first, then import to YouTube separately (solves session timeout issues with large libraries)
- **Automatic authorization** — the program opens a browser and captures authentication data automatically
- **Multithreading** — parallel track processing speeds up export and import up to 5x
- **Import mode selection** — fast parallel mode or order-preserving mode
- **Browser authentication** — more stable than OAuth, doesn't require creating a Google Cloud project

## Installation

```bash
git clone https://github.com/kirillqa17/yandex2ytmusic.git
cd yandex2ytmusic
pip install -r requirements.txt
playwright install chromium
```

## Usage

```bash
python main.py
```

An interactive menu will appear:

```
=== Yandex Music → YouTube Music ===

What do you want to do?
  1. Full transfer (export from Yandex + import to YouTube)
  2. Export from Yandex Music only
  3. Import to YouTube Music only (from file)
  4. Set up YouTube Music authorization

Choice (1-4):
```

When importing, you can choose the mode:

```
Import mode:
  1. Fast (parallel, order not preserved)
  2. Preserve order (slower)
```

## Detailed Instructions

### Step 1: Get Yandex Music Token

1. Go to [oauth.yandex.ru/authorize](https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d)
2. Sign in to your Yandex account
3. Copy the token from the URL (`access_token` parameter)

Or follow the [yandex-music documentation](https://yandex-music.readthedocs.io/en/main/token.html).

### Step 2: Export Tracks and podcasts from Yandex Music

```bash
python main.py
# Choose: 2. Export from Yandex Music only
# Enter token
```

Tracks, playlists and podcasts will be saved to `tracks.json`. Multithreaded processing speeds up the process ~5x.

### Step 3: Set Up YouTube Music Authorization

```bash
python main.py
# Choose: 4. Set up YouTube Music authorization
```

#### Option 1: Automatic via Browser (Recommended)

1. Choose option "1. Automatic from browser"
2. A browser will open — sign in to your Google account if needed
3. Wait for YouTube Music to load
4. The browser will close automatically after capturing data

The program will automatically capture the required headers and create `browser.json`.

#### Option 2: Manual (If Automatic Doesn't Work)

1. Open [music.youtube.com](https://music.youtube.com) (sign in)
2. Open DevTools (F12)
3. Go to the **Network** tab
4. Type `browse` in the filter
5. Click on any page in YouTube Music
6. Find a POST request to `browse?...` and click on it
7. Copy Request Headers:
   - **Firefox**: right-click → Copy Value → Copy Request Headers
   - **Chrome**: right-click → Copy → Copy request headers
8. Paste in terminal and press **Ctrl+D**

### Step 4: Import Tracks and Podcasts to YouTube Music

```bash
python main.py
# Choose: 3. Import to YouTube Music only (from file)
# Choose mode: 1 (fast) or 2 (preserve order)
```

The program will load, playlists and podcasts from `tracks.json` and add them to your YouTube Music likes.

## Import Modes

| Mode | Speed | Track Order |
|------|-------|-------------|
| Fast | ~5x faster | Random |
| Preserve order | Normal | Same as Yandex Music |

In both modes, **search** is performed in parallel (fast). The difference is only in adding likes.

## Recommended Order for Large Libraries

If you have many tracks (500+), it's recommended to split the process:

1. **Export** (option 2) — takes time, but doesn't depend on YouTube
2. **Set up authorization** (option 4) — do it right before import
3. **Import** (option 3) — do it immediately after setting up authorization

This solves the YouTube session timeout problem during long Yandex exports.

## tracks.json File Structure

```json
{
  "playlists": [
    {
      "title": "My favorite songs",
      "description": "Check out this playlist!",
      "tracks": [
        {
          "artist": "Queen",
          "name": "Bohemian Rhapsody"
        }
      ]
    }
  ],
  "liked_podcasts": [
    {
      "label": "Sample Podcast Label",
      "name": "Sample Podcast"
    }
  ],
  "liked_tracks": [
    {
      "artist": "Queen",
      "name": "Bohemian Rhapsody"
    }
  ],
  "not_found": [],
  "errors": []
}
```
- `playlists` — all playlists from Yanddex Music
- `liked_podcasts` — all podcasts from Yandex Music
- `liked_tracks` — all tracks from Yandex Music
- `not_found` — tracks not found on YouTube Music
- `errors` — tracks that encountered errors during import

## Troubleshooting

### 401 Unauthorized Error

YouTube session expired. Repeat step 3 (set up authorization).

### 400 Bad Request Error with OAuth

Use Browser authentication instead of OAuth. It's more stable.

### Automatic Authorization Doesn't Work

- Make sure Playwright is installed: `pip install playwright && playwright install chromium`
- Try the manual method (option 2)

## Dependencies

- [yandex-music](https://github.com/MarshalX/yandex-music-api) — Yandex Music API
- [ytmusicapi](https://github.com/sigma67/ytmusicapi) — YouTube Music API
- [playwright](https://playwright.dev/python/) — browser automation for authorization
- [tqdm](https://github.com/tqdm/tqdm) — progress bar

## License

MIT
