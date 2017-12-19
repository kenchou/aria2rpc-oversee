#!/usr/bin/env python3

import argparse
import json
import logging

from aria2rpc import Aria2RpcClient
from time import sleep


log_levels = {
    1: logging.INFO,
    2: logging.DEBUG,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--jsonrpc', default='http://localhost:6800/jsonrpc', help='aria2 json rpc server')
    parser.add_argument('--token', help='Secret string')
    parser.add_argument('-v', '--verbose', action='count', default=1, help='increase output verbosity')

    args = parser.parse_args()

    logging.basicConfig(level=log_levels.get(args.verbose, 1))
    logger = logging.getLogger(__name__)

    aria2 = Aria2RpcClient(url=args.jsonrpc, token=args.token)

    statistics = {}
    while True:
        queue = []
        logger.info('Loop')

        response = aria2.tellActive()

        if not response.has_error():
            print('"""{:16}\t{:12}\t{:12}\t{:9}(%)\t{:9}"""'.format('GID', 'Completed', 'Total', 'Progress', 'Speed'))

            for task in response.result:
                gid = task['gid']
                completed_length = int(task['completedLength'])
                download_speed = task['downloadSpeed']
                total_length = int(task['totalLength'])

                print('"""{}\t{:12}\t{:12}\t{:9.2f}%\t{:9d}"""'.format(
                    gid,
                    completed_length, total_length, completed_length/total_length*100 if total_length else 0,
                    int(download_speed)))

                s = statistics.setdefault(gid, {'completed-length': 0})
                prev_length = s.get('completed-length', 0)
                if completed_length - prev_length == 0:
                    # TODO: compute avg download speed
                    retry = True
                    while retry:
                        r = aria2.pause(gid)
                        logger.info(r)
                        retry = r.has_error()
                        if retry:
                            sleep(1)
                    retry = True
                    while retry:
                        r = aria2.unpause(gid)
                        retry = r.has_error()
                        logger.info(r)
                        if retry:
                            sleep(1)
                    queue.append(gid)
                s['completed-length'] = completed_length

            position = 1000
            for gid in queue:
                position += 1
                r = aria2.changePosition(gid, position, 'POS_SET')
                logger.info(r)

            print('""" waiting """')
            response = aria2.tellWaiting(0, 20)
            # print(r.text)
            for task in response.result:
                gid = task['gid']
                completed_length = int(task['completedLength'])
                download_speed = task['downloadSpeed']
                total_length = int(task['totalLength'])
                print('"""{}\t{:12}\t{:12}\t{:9.2f}%\t{:9d}"""'.format(
                    gid,
                    completed_length, total_length, completed_length/total_length*100 if total_length else 0,
                    int(download_speed)))
        sleep(300)
