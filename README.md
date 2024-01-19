# yandex2ytmusic

**[English](README_EN.md)**

Перенос понравившихся треков из Yandex.Музыка в YouTube Music.

## Интерфейс программы

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

## Использование

1. [Получить Yandex Music token](https://yandex-music.readthedocs.io/en/main/token.html). Легче всего это сделать с помошью приложения.
2. Установить зависимости и запустить программу:
```bash
pip install -r requirements.txt
python main.py --yandex <Yandex Music token>
```
3. При запуске программы перейти по предложенной ссылке для авторизации в YouTube Music, разрешить доступ к аккаунту и нажать `Enter` для продолжения.
4. Дождаться завершения работы программы. Программа также экспортирует музыку Json в файл:

```json
{
    // понравившиеся треки в Yandex Music
    "liked_tracks":[
        {
            "artist": "Исполнитнль",
            "name": "Название трека"
        }
    ],
    // треки, которые не были найдены при переносе
    "not_found":[], 
    // треки, при переносе которых произошла ошибка
    "errors":[]
}
```

## Используемые ресурсы

- yandex-music - не официальное python API Yandex.Music
- ytmusicapi - не официальное python API YouTube Music

### P.s.

Написал этот скрипт, так как не нашел ничего подобного в сети.
Буду рад pull реквестам и звездочкам :-)

