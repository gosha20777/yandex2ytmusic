import argparse
import json

from core import YandexMusicExporter
from core import YoutubeImoirter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Transfer tracks from Yandex.Music to YouTube Music'
    )
    parser.add_argument(
        '--yandex', type=str, help='Yandex Music token'
    )
    parser.add_argument(
        '--output', type=str, default='tracks.json', help='Output json file'
    )
    parser.add_argument(
        '--youtube', type=str, default='youtube.json', 
        help='Youtube Music credentials file. If file not exists, it will be created.'
    )
    return parser.parse_args()


def move_tracks(
        importer: YandexMusicExporter, exporter: YoutubeImoirter, out_path: str
    ) -> None:
    data = {
        'liked_tracks': [],
        'not_found': [],
        'errors': [],
    }
    
    print('Exporting liked tracks from Yandex Music...')
    tracks = importer.export_liked_tracks()
    tracks.reverse()

    for track in tracks:
        data['liked_tracks'].append({
            'artist': track.artist,
            'name': track.name
        })

    print('Importing liked tracks to Youtube Music...')
    not_found, errors = exporter.import_liked_tracks(tracks)

    for track in not_found:
        data['not_found'].append({
            'artist': track.artist,
            'name': track.name
        })
        print(f'{track.artist} - {track.name}')
    
    for track in errors:
        data['errors'].append({
            'artist': track.artist,
            'name': track.name
        })
    
    print(f'{len(not_found)} not found tracks, {len(errors)} errors.')

    str_data = json.dumps(data)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(str_data)


def main() -> None:
    args = parse_args()
    importer = YandexMusicExporter(args.yandex)
    exporter = YoutubeImoirter(args.youtube)
    move_tracks(importer, exporter, args.output)


if __name__ == '__main__':
    main()