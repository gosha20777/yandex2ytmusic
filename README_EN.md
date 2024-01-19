# yandex2ytmusic

**[Русский язык](README.md)**

Transfer liked tracks from Yandex.Music to YouTube Music.

## Program Interface

```bash
python main.py --help                                                         
usage: main.py [-h] [--yandex YANDEX] [--output OUTPUT] [--youtube YOUTUBE]

Transfer tracks from Yandex.Music to YouTube Music

options:
  -h, --help         show this help message and exit
  --yandex YANDEX    Yandex Music token
  --output OUTPUT    Output json file
  --youtube YOUTUBE  Youtube Music credentials file. If file not exists, it will be created.
```

## Usage

1. [Get Yandex Music token](https://yandex-music.readthedocs.io/en/main/token.html). It is easiest to do this with the application.
2. Install dependencies and run the program:

```bash
pip install -r requirements.txt
python main.py --yandex <Yandex Music token>
```

3. When starting the program, follow the provided link to authorize in YouTube Music, allow access to the account, and press `Enter` to continue.
4. Wait for the program to finish. The program will also export music data to a JSON file:

```json
{
    // liked tracks in Yandex Music
    "liked_tracks":[
        {
            "artist": "Artist",
            "name": "Track Name"
        }
    ],
    // tracks not found during transfer
    "not_found":[], 
    // tracks that encountered an error during transfer
    "errors":[]
}
```

## Resources Used

- yandex-music - unofficial python API for Yandex.Music
- ytmusicapi - unofficial python API for YouTube Music

### P.S.

I wrote this script because I couldn't find anything similar online.
I'll be happy with pull requests and stars :-)
