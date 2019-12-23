#!/usr/bin/env python

import click
import json
import math
import os.path
import torrent_parser as tp


def sizeof_fmt(num, suffix='B'):
    magnitude = int(math.floor(math.log(num, 1024)))
    val = num / math.pow(1024, magnitude)
    if magnitude > 7:
        return '{:.1f}{}{}'.format(val, 'Yi', suffix)
    return '{:3.1f}{}{}'.format(val, ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi'][magnitude], suffix)


@click.command()
@click.option('-l', '--file-list', is_flag=True, help='File list.')
@click.argument('url-or-torrent-path', nargs=-1, required=True)
def main(file_list, url_or_torrent_path):
    for uri in url_or_torrent_path:
        torrent = tp.parse_torrent_file(uri)
        if file_list:
            if 'files' in torrent['info']:
                for file_info in torrent['info']['files']:
                    include_path = len(file_info['path']) > 1
                    file_path = os.path.join(*file_info['path'])
                    file_length = file_info["length"]
                    click.echo(f'{os.path.basename(uri)}\t{sizeof_fmt(file_length)}\t{file_path}')
            pass
        else:
            print(json.dumps(torrent, sort_keys=True, indent=4))


if __name__ == '__main__':
    main()
