#!/usr/bin/env python

import click
import json
import torrent_parser as tp


@click.command()
@click.argument('url-or-torrent-path', nargs=-1, required=True)
def main(url_or_torrent_path):
    for uri in url_or_torrent_path:
        data = tp.parse_torrent_file(uri)
        # print(f'"{data.keys()}"')
        print(json.dumps(data, sort_keys=True, indent=4))


if __name__ == '__main__':
    main()
