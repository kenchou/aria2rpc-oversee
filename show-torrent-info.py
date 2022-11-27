#!/usr/bin/env python

import click
import json
import math
import torrent_parser as tp

from pathlib import Path


units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]


def sizeof_fmt(num):
    magnitude = int(math.floor(math.log(num, 1024)))
    val = num / math.pow(1024, magnitude)
    unit = units[min(magnitude, len(units) - 1)]
    return f"{val:4.1f}{unit:<3}"


@click.command()
@click.option("-l", "-ls", "--file-list", is_flag=True, help="File list.")
@click.argument("url-or-torrent-path", nargs=-1, required=True)
def main(file_list, url_or_torrent_path):
    for uri in url_or_torrent_path:
        torrent = tp.parse_torrent_file(uri)
        if file_list:
            if "files" in torrent["info"]:
                for file_info in torrent["info"]["files"]:
                    file_path = Path(*file_info["path"])
                    file_length = file_info["length"]
                    click.echo(f"{Path(uri).name}\t{sizeof_fmt(file_length):>8}\t{file_path}")
            pass
        else:
            print(json.dumps(torrent, sort_keys=True, indent=4))


if __name__ == "__main__":
    main()
