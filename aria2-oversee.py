#!/usr/bin/env python3

import argparse
import json

from aria2rpc import Aria2RpcClient
from time import sleep


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--jsonrpc', default='http://localhost:6800/jsonrpc', help='aria2 json rpc server')
    parser.add_argument('--token', help='Secret string')

    args = parser.parse_args()

    aria2 = Aria2RpcClient(url=args.jsonrpc, token=args.token)

    statistics = {}
    while True:
        print('"""--------"""')

        r = aria2.tellActive()

        # print(r.text)
        print('"""{:16}\t{:12}\t{:12}\t{:9}(%)\t{:9}"""'.format('GID', 'Completed', 'Total', 'Progress', 'Speed'))
        result = json.loads(r.text)
        for task in result['result']:
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
                r = aria2.pause(gid)
                print(r.text)
                # change position
                r = aria2.changePosition(gid, 1000, 'POS_SET')
                print(r.text)
                r = aria2.unpause(gid)
                print(r.text)
            s['completed-length'] = completed_length

        r = aria2.tellWaiting(0, 20)
        # print(r.text)
        result = json.loads(r.text)
        for task in result['result']:
            gid = task['gid']
            completed_length = int(task['completedLength'])
            download_speed = task['downloadSpeed']
            total_length = int(task['totalLength'])
            print('"""{}\t{:12}\t{:12}\t{:9.2f}%\t{:9d}"""'.format(
                gid,
                completed_length, total_length, completed_length/total_length*100 if total_length else 0,
                int(download_speed)))
        sleep(60)
