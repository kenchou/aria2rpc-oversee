import json
import requests

from baseconv import base36


class Aria2RpcClient:
    def __init__(self, url='http://localhost:6800/jsonrpc', token=None):
        self.url = url
        self.token = token
        self._uniq_id = 0

    def __getattr__(self, item):
        def _function(*args, **kwargs):
            print('""">>> You tried to call a method named: %s, args:' % item, *args, kwargs, '"""')
            return self.request(item, args, **kwargs)
        return _function

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
        # print(params)
        # print('===>')
        # print(json.dumps(params))
        return requests.post(self.url, json.dumps(params))
