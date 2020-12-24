# ~/callbacks.py

import aria2p
import logging
import subprocess
from pathlib import Path


def on_download_error(api, gid):
    # pop a desktop notification using notify-send
    download = api.get_download(gid)
    summary = f"A download failed"
    body = f"{download.name}\n{download.error_message} (code: {download.error_code})."
    subprocess.call(["notify-send", "-t", "10000", summary, body])


def on_download_complete(api, gid):
    task: aria2p.downloads.Download
    task = api.get_download(gid)
    # purge if it was a magnet metadata download
    if task.is_metadata:
        logging.info(f'Purge Complete metadata {task.gid}: "{task.name}".')
        task.purge()
        return
    # move files from tmp dir to another
    if '.tmp' == task.dir.name:
        destination = Path(task.dir.parent)
        logging.info(f'Complete {task.gid}: move "{task.name}" from {task.dir} to {destination}')
        if task.move_files(destination):
            task.control_file_path.unlink()
            task.purge()
