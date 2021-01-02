import aria2p
import json
import logging
import signal

from pathlib import Path
from time import sleep


DEFAULT_CONFIG_PATH = '.aria2'
DEFAULT_ARIA2_CONFIG = 'aria2rpc.json'
DEFAULT_TORRENT_EXCLUDE_LIST_FILE = 'torrent_clean.lst'
DEFAULT_ARIA2_HOST = 'http://localhost'
DEFAULT_ARIA2_PORT = 6800
DEFAULT_ARIA2_JSONRPC = f'{DEFAULT_ARIA2_HOST}:{DEFAULT_ARIA2_PORT}/jsonrpc'
LOG_LEVELS = {
    0: logging.WARNING,
    1: logging.INFO,
    2: logging.DEBUG,
}


def uniq_list_keep_order(seq):
    """get a uniq list and keep the elements order"""
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def guess_path(test_file, guess_paths=None):
    """test the file exists in one of guess paths"""
    if test_file is None:
        return
    test_file = Path(test_file).expanduser()
    if guess_paths is None:
        guess_paths = [
            Path.cwd(),  # current dir
            Path.home(),  # home dir
            Path(__file__).parent.parent,  # script dir
        ]
    for p in uniq_list_keep_order([Path(p).resolve() for p in guess_paths]):
        file_path = p / test_file
        if file_path.is_file():
            return file_path
    return


def get_config(filename):
    if filename is None:
        return None
    try:
        with open(filename) as f:
            config = json.load(f)
            return config
    except IOError as e:
        logging.warning(e)
        return None


def change_status(action):
    try:
        action()
    except aria2p.client.ClientException as e:
        logging.error('ClientException: ' + str(e))


class Aria2QueueManager:
    """Queue Manager"""
    def __init__(self, aria2rpc, exit_event):
        self.queue = []
        self.statistics = {}
        self.aria2rpc = aria2rpc
        self.exit_event = exit_event

    def get_data(self):
        logging.debug('Fetch tasks from RPC')
        downloads = self.aria2rpc.get_downloads()
        task_active = []
        task_waiting = []
        for download in downloads:
            if download.is_active:
                task_active.append(download)
            elif download.is_waiting:
                task_waiting.append(download)
            elif download.is_complete:
                continue
            logging.info(
                f"{download.gid:<17} "
                f"{download.status:<9} "
                f"{download.progress_string():>8} "
                f"{download.download_speed_string():>12} "
                f"{download.upload_speed_string():>12} "
                f"{download.eta_string():>8}  "
                f"{download.name}"
            )
        return task_active, task_waiting

    def run(self):
        task_active, task_waiting = self.get_data()
        if task_waiting:
            self.update(task_active, len(task_waiting))
        else:
            logging.info('No waiting tasks')

    def task_wait_status(self, task, status):
        while not self.exit_event.is_set() and not getattr(task.live, status):
            logging.debug(f'> Waiting status changes, current status: {task.status}')
            self.exit_event.wait(5)

    def update(self, task_list, task_count):
        """
        Strategy of task swap: download size
        :param task_list: [aria2p.downloads.Download]
        :param task_count: int
        :return:
        """
        task: aria2p.downloads.Download
        cnt = 0
        for task in task_list:
            gid = task.gid
            completed_length = task.completed_length
            s = self.statistics.setdefault(gid, {'completed-length': 0, 'increment': 0})
            prev_length = s.get('completed-length', 0)
            increment = completed_length - prev_length
            s['completed-length'] = completed_length
            s['increment'] = increment
            if not increment:
                logging.info(f'swap {cnt}/{task_count}: {task.gid} "{task.name}" move to bottom')

                change_status(task.pause)
                self.task_wait_status(task, 'is_paused')
                logging.debug(f'> CNT: {cnt}/{task_count}: {task.gid} -> {task.status=}')

                self.exit_event.wait(1)

                change_status(task.resume)
                self.task_wait_status(task, 'is_waiting')
                logging.debug(f'> CNT: {cnt}/{task_count}: {task.gid} -> {task.status=}')

                task.move_to_bottom()
                cnt += 1
                if cnt >= task_count:
                    break
