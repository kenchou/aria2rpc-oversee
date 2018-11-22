#!/usr/bin/env python3

import click
import click_log
import logging

from aria2rpc import Aria2RpcClient, DEFAULT_ARIA2_JSONRPC
from aria2rpc.config import get_config
from time import sleep


ARIA2_CONFIG = '.config/aria2rpc.json'

log_levels = {
    0: logging.WARNING,
    1: logging.INFO,
    2: logging.DEBUG,
}


def try_call(func, *args, **kwargs):
    _MAX_DELAY_TIME = 5
    logger = logging.getLogger('try_call')
    _sleep_time = 0
    _retry = True
    while _retry:
        _res = func(*args, **kwargs)
        logger.info('%s%s: %s', func.__name__, args, _res)
        _retry = _res.error
        if _retry:
            _sleep_time += 1 if _sleep_time <= _MAX_DELAY_TIME else 0
            sleep(_sleep_time)


@click.command()
@click.option('--json-rpc', help='Aria2 JSON-RPC server. default: {}'.format(DEFAULT_ARIA2_JSONRPC))
@click.option('--token', help='RPC SECRET string')
@click.option('-v', '--verbose', count=True, help='Increase output verbosity.')
def run(json_rpc, token, verbose):
    logging.basicConfig(level=log_levels.get(verbose, logging.INFO))
    logger = logging.getLogger(__name__)

    config = get_config(ARIA2_CONFIG, {'json-rpc': DEFAULT_ARIA2_JSONRPC})

    if not json_rpc:
        json_rpc = config.get('json-rpc', DEFAULT_ARIA2_JSONRPC)
    if not token:
        token = config.get('token')

    aria2 = Aria2RpcClient(url=json_rpc, token=token)

    statistics = {}
    while True:
        queue = []
        logger.info('Loop')

        response = aria2.tellActive()

        if not response.error:
            print('"{:16}\t{:12}\t{:12}\t{:9}(%)\t{}"'.format('GID', 'Completed', 'Total', 'Progress', 'Speed'))

            for task in response.result:
                gid = task['gid']
                completed_length = int(task['completedLength'])
                download_speed = task['downloadSpeed']
                total_length = int(task['totalLength'])

                print('"{}\t{:12}\t{:12}\t{:9.2f}%\t{:9d}"'.format(
                    gid,
                    completed_length, total_length, completed_length/total_length*100 if total_length else 0,
                    int(download_speed)))

                s = statistics.setdefault(gid, {'completed-length': 0})
                prev_length = s.get('completed-length', 0)
                if completed_length - prev_length == 0:
                    # TODO: compute avg download speed
                    try_call(aria2.pause, gid)
                    try_call(aria2.unpause, gid)
                    queue.append(gid)
                s['completed-length'] = completed_length

            position = 1000
            for gid in queue:
                position += 1
                r = aria2.changePosition(gid, position, 'POS_SET')
                logger.info('%s(%s, %s, %s): %s', 'changePosition', gid, position, 'POS_SET', r)

            print('""" waiting """')
            response = aria2.tellWaiting(0, 20)
            # print(r.text)
            for task in response.result:
                gid = task['gid']
                completed_length = int(task['completedLength'])
                download_speed = task['downloadSpeed']
                total_length = int(task['totalLength'])
                print('"{}\t{:12}\t{:12}\t{:9.2f}%\t{:9d}"'.format(
                    gid,
                    completed_length, total_length, completed_length/total_length*100 if total_length else 0,
                    int(download_speed)))
        logger.info('sleep(300)')
        sleep(300)


if __name__ == "__main__":
    run()
