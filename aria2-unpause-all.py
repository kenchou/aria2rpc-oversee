#!/usr/bin/env python3

import click
import json
from aria2rpc import Aria2RpcClient, DEFAULT_ARIA2_JSONRPC


@click.command()
@click.option('--json-rpc', help='Aria2 JSON-RPC server. default: {}'.format(DEFAULT_ARIA2_JSONRPC))
@click.option('--token', help='RPC SECRET string')
# @click.option('-v', '--verbose', count=True, help='Increase output verbosity.')
def unpause_all(json_rpc, token):
    aria2 = Aria2RpcClient(url=json_rpc, token=token)

    r = aria2.tellActive()
    print("### Active ###")
    print('{:64}\t{}\t{}\t{}\t{}%'.format('Name', 'Download Speed', 'Length', 'Total Length', 'Percent'))
    # print(r)
    for item in r.result:
        # print(item)
        # print(item['bittorrent'].keys())
        title = item['bittorrent']['info']['name'] if 'info' in item['bittorrent'] else item['infoHash']
        progress = int(item['completedLength']) / int(item['totalLength']) * 100 if int(item['totalLength']) else 0
        print('{:64}\t{}\t{}\t{}\t{:2.2f}%'.format(title,
                                                   item['downloadSpeed'],
                                                   item['completedLength'],
                                                   item['totalLength'],
                                                   progress))
    r = aria2.unpauseAll()
    print(r)

    # r = aria2.tellWaiting(0, 100)
    print("### Waiting ###")
    # print(r)


if __name__ == "__main__":
    unpause_all()
