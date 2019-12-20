#!/usr/bin/env python3

import base64
import click
import click_log
import logging
import os.path
import re

from aria2rpc import Aria2RpcClient
from aria2rpc.config import get_config
from fnmatch import fnmatch
from torrent_parser import TorrentFileParser, InvalidTorrentDataException


ARIA2_CONFIG = '.config/aria2rpc.json'
DEFAULT_ARIA2_JSONRPC = 'http://localhost:6800/jsonrpc'
PATTERN_SUPPORTED_URI = re.compile('(http(s)?|ftp(s)|sftp)://|magnet:')


# init logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
click_log.basic_config(logger)


def is_supported_uri(uri):
    return PATTERN_SUPPORTED_URI.match(uri)


def is_torrent_file(filename):
    return '.torrent' == os.path.splitext(filename)[1]


def is_aria2_file(filename):
    return '.aria2' == os.path.splitext(filename)[1]


@click.command()
@click.option('--json-rpc', help='Aria2 JSONRPC server.')
@click.option('--token', help='RPC SECRET string')
@click.option('-d', '--download-dir', help="The directory to store the downloaded file.")
@click.option('-x', '--exclude-file', default='clean.lst', type=click.File('r'), help="path to file of exclude list.")
@click.option('--pause', is_flag=True, help='Pause download after added.')
@click.argument('url-or-torrent-path', nargs=-1, required=True)
def main(json_rpc, token, download_dir, exclude_file, pause, url_or_torrent_path):
    """Aria2 RPC Client"""
    config = get_config(ARIA2_CONFIG, {'json-rpc': DEFAULT_ARIA2_JSONRPC})

    if not json_rpc:
        json_rpc = config.get('json-rpc', DEFAULT_ARIA2_JSONRPC)
    if not token:
        token = config.get('token')

    # exclude list
    exclude_patterns = []
    if exclude_file:
        for line in exclude_file:
            line = line.strip()
            if not line or '#' == line[1]:    # skip empty lines or comment
                continue
            exclude_patterns.append(line)

    aria2 = Aria2RpcClient(json_rpc, token=token)

    options = {}
    if download_dir:
        options['dir'] = download_dir
    if pause:
        options['pause'] = pause

    for uri in url_or_torrent_path:
        click.echo(f'## process {uri}')
        if is_supported_uri(uri):
            # aria2.addUri([secret, ]uris[, options[, position]])
            # @see https://aria2.github.io/manual/en/html/aria2c.html#aria2.addUri
            response = aria2.addUri([uri], options)
            click.echo(response)
            pass
        elif is_torrent_file(uri):
            try:
                with open(uri, 'rb') as f:
                    # parse torrent file
                    torrent = TorrentFileParser(f, use_ordered_dict=True).parse()
                    if 'files' in torrent['info']:  # filter if there is multi-files torrent
                        selected = []
                        for idx, file_info in enumerate(torrent['info']['files']):
                            # print(idx, file_info)
                            include_path = len(file_info['path']) > 1
                            file_path = os.path.join(*file_info['path'])
                            file_length = file_info["length"]
                            _lower_file_path = file_path.lower()    # for fnmatch case-insensitive
                            for p in exclude_patterns:
                                exclude_pattern = os.path.join('*', p) if include_path else p
                                if fnmatch(_lower_file_path, exclude_pattern.lower()):
                                    click.secho(f'{uri}, match: {exclude_pattern}, '
                                                f'skip file: "{file_path}", len: {file_length}, ',
                                                err=True, fg='yellow')
                                    break
                            else:
                                click.secho(f'{uri}, selected {idx}, file: "{file_path}", len: {file_length}',
                                            fg='green')
                                selected.append(idx)
                    if selected:
                        options['select-file'] = ','.join(selected)
                    f.seek(0)   # rewind the file
                    # aria2.addTorrent([secret, ]torrent[, uris[, options[, position]]])
                    # @see https://aria2.github.io/manual/en/html/aria2c.html#aria2.addTorrent
                    response = aria2.addTorrent(base64.b64encode(f.read()).decode('utf-8'), [], options)
                    click.echo(response)
            except InvalidTorrentDataException as e:
                click.secho(f'skip torrent file: "{uri}", reason: {e}', err=True, fg='yellow')
                continue
        elif is_aria2_file(uri):
            # TODO: parse .aria2 file and add magnet URI
            click.secho(f'Not currently supported file "{uri}"', err=True, fg='red')
        else:
            click.secho(f'Unknown file "{uri}"', err=True, fg='red')


if __name__ == '__main__':
    main()
