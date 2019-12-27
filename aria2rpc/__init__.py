import json
import requests

from baseconv import base36
from pathlib import Path


DEFAULT_CONFIG_PATH = '.aria2'
DEFAULT_ARIA2_CONFIG = 'aria2rpc.json'
DEFAULT_TORRENT_EXCLUDE_LIST_FILE = 'torrent_clean.lst'
DEFAULT_ARIA2_JSONRPC = 'http://localhost:6800/jsonrpc'


def uniq_list_keep_order(seq):
    """get a uniq list and keep the elements order"""
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def guess_path(test_file, guess_paths=None):
    """test the file exists in one of guess paths"""
    if test_file is None:
        return
    if guess_paths is None:
        guess_paths = [
            Path.cwd(),  # current dir
            Path.home(),  # home dir
            Path(__file__).parent.parent,  # script dir
        ]
    for p in uniq_list_keep_order(guess_paths):
        file_path = p / test_file
        if file_path.is_file():
            return file_path
    return


def get_config(filename):
    with open(filename) as f:
        config = json.load(f)
        return config


class Aria2RpcClient:
    def __init__(self, url=None, token=None):
        self.url = url or DEFAULT_ARIA2_JSONRPC
        self.token = token
        self._uniq_id = 0
        self.last_response = None

    def __getattr__(self, method):
        def _request(*args):
            _request.__name__ = method
            # print('""">>> You tried to call a method named: %s, args:' % method, *args, kwargs, '"""')
            return self.request(method, args)
        return _request

    def request(self, method, data=None):
        if data is None:
            data = []
        else:
            data = list(data)
        if self.token:
            data = ['token:{}'.format(self.token)] + data
        self._uniq_id += 1

        method = "aria2.{}".format(method) if '_' not in method else method.replace('_', '.')

        params = {
            'jsonrpc': '2.0',
            'id': base36.encode(self._uniq_id),
            'method': method,
            'params': data,
        }

        self.last_response = requests.post(self.url, json.dumps(params))
        return Aria2RpcResponse(json.loads(self.last_response.text))


class Aria2RpcResponse:
    def __init__(self, response_data):
        self.response = response_data

    @property
    def error(self):
        return self.response.get('error')

    @property
    def result(self):
        return self.response.get('result')

    def __str__(self):
        return json.dumps(self.response)


def get_task_name(task):
    if 'bittorrent' in task:
        return task['bittorrent']['info']['name']
    elif 'files' in task:
        return ','.join([Path(f['path']).name for f in task['files']])
    else:
        return None


def print_status(response, title=None):
    if response.error:
        print(response.error)
        return
    if title:
        print(title)
    # print(response)
    print('{:16}\t{}\t{:12}\t{:12}\t{:9}(%)\t{}'.format('GID', 'Completed', 'Total', 'Progress', 'Speed', 'Task_Name'))
    for task in response.result:
        # print('>>> task', json.dumps(task))
        gid = task['gid']
        task_name = get_task_name(task)
        completed_length = int(task['completedLength'])
        download_speed = task['downloadSpeed']
        total_length = int(task['totalLength'])
        print('{}\t{:12}\t{:12}\t{:9.2f}%\t{:9d}\t{}'.format(
            gid,
            completed_length,
            total_length,
            completed_length / total_length * 100 if total_length else 0,
            int(download_speed),
            task_name,
        ))
