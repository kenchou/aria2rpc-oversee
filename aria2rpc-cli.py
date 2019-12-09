#!/usr/bin/env python3

import base64
import click
import click_log
import logging
import re

from aria2rpc import Aria2RpcClient
from aria2rpc.config import get_config


ARIA2_CONFIG = '.config/aria2rpc.json'
DEFAULT_ARIA2_JSONRPC = 'http://localhost:6800/jsonrpc'


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
click_log.basic_config(logger)


pattern = re.compile('(http(s)?|ftp|sftp|ftps)://|magnet:')


def is_url(uri):
    return pattern.match(uri)


def is_torrent(f):
    return True


def is_aria2_session(f):
    pass


@click.command()
@click.option('--json-rpc', help='Aria2 JSONRPC server.')
@click.option('--token', help='RPC SECRET string')
@click.option('-d', '--download-dir', help="The directory to store the downloaded file.")
@click.option('--pause', is_flag=True, help='Pause download after added.')
@click.argument('url-or-torrent-path', nargs=-1, required=True)
def main(json_rpc, token, download_dir, pause, url_or_torrent_path):
    """Aria2 RPC Client"""
    config = get_config(ARIA2_CONFIG, {'json-rpc': DEFAULT_ARIA2_JSONRPC})

    if not json_rpc:
        json_rpc = config.get('json-rpc', DEFAULT_ARIA2_JSONRPC)
    if not token:
        token = config.get('token')

    aria2 = Aria2RpcClient(json_rpc, token=token)

    options = {}
    if download_dir:
        options['dir'] = download_dir
    if pause:
        options['pause'] = pause

    for uri in url_or_torrent_path:
        if is_url(uri):
            response = aria2.addUri([uri], options)
            print(response)
            pass
        else:
            with open(uri, 'rb') as f:
                if is_torrent(f):
                    torrent = base64.b64encode(f.read()).decode('utf-8')
                    response = aria2.addTorrent(torrent, [], options)
                    print(response)
                elif is_aria2_session(f):
                    pass
                else:
                    print('unknown file')


if __name__ == '__main__':
    main()
