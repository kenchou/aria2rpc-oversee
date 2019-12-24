import json
from pathlib import Path


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
