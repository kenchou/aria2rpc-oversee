import aria2p
import json
import logging

from pathlib import Path


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
logger = logging.getLogger(__name__)


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


def load_config_file(filename):
    if filename is None:
        return None
    try:
        with open(filename) as f:
            config = json.load(f)
            return config
    except IOError as e:
        logger.warning(e)
        return None


def load_aria2_config(config_file, guess_paths=None):
    if guess_paths is None:
        guess_paths = [
            Path.home() / DEFAULT_CONFIG_PATH,  # ~/.aria2/
            Path(__file__).resolve().parent.parent / DEFAULT_CONFIG_PATH,  # ${BIN_PATH}/.aria2/
        ]
    config_file_path = guess_path(config_file, guess_paths) or guess_path(DEFAULT_ARIA2_CONFIG, guess_paths)
    if config_file_path is None:
        logger.error(f'--config-file "{config_file}" not found in paths: {[str(p) for p in guess_paths]}')
        config = {'host': DEFAULT_ARIA2_HOST, 'port': DEFAULT_ARIA2_PORT}
    else:
        config = load_config_file(config_file_path)
    return config


class Aria2QueueManager:
    """Queue Manager"""
    def __init__(self, aria2rpc, exit_event):
        self.queue = []
        self.statistics = {}
        self.aria2rpc = aria2rpc
        self.exit_event = exit_event
        self.logger = logging.getLogger(f'{__name__}.{self.__class__.__name__}')

    def get_data(self):
        self.logger.debug(f'Fetch tasks from RPC')
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
            self.logger.info(
                f"{download.gid:<17} "
                f"{download.status:<9} "
                f"{download.progress_string():>8} "
                f"{download.download_speed_string():>12} "
                f"{download.upload_speed_string():>12} "
                f"{download.eta_string():>8}  "
                f"{download.name}"
            )
        self.logger.info(f'Task Active: {len(task_active)}, Waiting: {len(task_waiting)}')
        return task_active, task_waiting

    def change_task_status(self, task, status, condition, hint=None):
        if self.exit_event.is_set():
            return False
        self.logger.debug(f'>>> task( {task.gid} ).{status}()')
        try:
            getattr(task, status)()     # call status()
        except aria2p.client.ClientException as e:
            self.logger.error('ClientException: ' + str(e))
        # wait status changed
        n = 0
        while not self.exit_event.is_set():
            if condition(task):
                self.logger.debug(f'>>> task( {task.gid} ).status={task.status}, meet the condition <{hint}>')
                return True
            delay = min(2**n, 10)
            n += 1
            self.logger.debug(f'>>> task( {task.gid} ).status={task.status}, wait {delay}s for status {hint}')
            self.exit_event.wait(delay)
        else:
            return False

    def update(self, task_list, task_count):
        """
        Strategy of task swap: download size
        :param task_list: [aria2p.downloads.Download]
        :param task_count: int
        :return:
        """
        task: aria2p.downloads.Download
        swap_count = 0
        for idx, task in enumerate(task_list, start=1):
            gid = task.gid
            completed_length = task.completed_length
            s = self.statistics.setdefault(gid, {'completed-length': 0, 'increment': 0})
            prev_length = s.get('completed-length', 0)
            increment = completed_length - prev_length
            s['completed-length'] = completed_length
            s['increment'] = increment
            # self.logger.debug(f'* {gid}: {increment}')
            if not increment:
                swap_count += 1
                self.logger.info(f'{idx}: swap out ({swap_count}/{task_count}) task {task.gid} "{task.name}"')

                if not self.change_task_status(task, 'pause', condition=lambda d: d.live.is_paused, hint='paused'):
                    self.logger.warning(f'Program is exiting. And the task( {task.gid} ) is switching to the pause status, '
                                    f'which may cause the status of the task to not resume normally')
                    break
                self.logger.debug(f'task( {task.gid} ) move to bottom')
                task.move_to_bottom()
                # self.exit_event.wait(1)
                if not self.change_task_status(task, 'resume',
                                               condition=lambda d: not d.live.is_paused, hint='not paused'):
                    break
                if swap_count >= task_count:
                    break
        if swap_count:
            self.logger.info(f'Swap {swap_count} tasks. Good luck!')
        else:
            self.logger.info('No need to swap, all tasks are downloading ^_^')

    def run(self):
        task_active, task_waiting = self.get_data()
        if task_waiting:
            self.update(task_active, len(task_waiting))
        else:
            self.logger.info('No waiting tasks')
