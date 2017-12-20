#!/usr/bin/env python3

import base64
import click
import click_log
import json
import logging
import os.path

from aria2rpc import Aria2RpcClient
from aria2rpc.config import get_config


ARIA2_CONFIG = '.config/aria2rpc.json'
DEFAULT_ARIA2_JSONRPC = 'http://localhost:6800/jsonrpc'


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
click_log.basic_config(logger)


@click.command()
@click.option('--jsonrpc', help='Aria2 JSONRPC server.')
@click.option('--token', help='RPC SECRET string')
@click.option('--dir', 'download_dir', help="The directory to store the downloaded file.")
@click.option('--pause', is_flag=True, help='Pause download after added.')
@click.argument('torrent-file', type=click.File('rb'), nargs=-1, required=True)
def main(jsonrpc, token, download_dir, pause, torrent_file):
    """Aria2 RPC Client"""
    config = get_config(ARIA2_CONFIG, {'json-rpc': DEFAULT_ARIA2_JSONRPC})

    if not jsonrpc:
        jsonrpc = config.get('json-rpc')
    if not token:
        token = config.get('token')

    aria2 = Aria2RpcClient(jsonrpc, token=token)

    option = {}
    if dir:
        option['dir'] = download_dir
    if pause:
        option['pause'] = pause
    for f in torrent_file:
        torrent = base64.b64encode(f.read()).decode('utf-8')
        response = aria2.addTorrent(torrent, [], option)
        print(response)


if __name__ == '__main__':
    main()
