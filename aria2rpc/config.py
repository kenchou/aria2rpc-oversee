import json
import os.path


def get_config(filename, default=None):
    guess = [os.path.join(os.path.expanduser("~")), os.path.dirname(os.path.dirname(__file__))]
    for path in guess:
        try:
            with open(os.path.join(path, filename), 'r') as f:
                config = json.load(f)
            return config
        except IOError:
            continue
    if default is None:
        raise IOError('Cannot found config in [{}].'.format(', '.join(map(lambda x: os.path.join(x, filename), guess))))
    else:
        return default
