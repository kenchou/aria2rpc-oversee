# ~/callbacks.py
import subprocess
from pathlib import Path


def on_download_error(api, gid):
    # pop a desktop notification using notify-send
    download = api.get_download(gid)
    summary = f"A download failed"
    body = f"{download.name}\n{download.error_message} (code: {download.error_code})."
    subprocess.call(["notify-send", "-t", "10000", summary, body])


def on_download_complete(api, gid):
    download = api.get_download(gid)
    # purge if it was a magnet metadata download
    if download.is_metadata:
        download.purge()
        return
    # move files to another folder
    destination = Path(download.dir) / "Completed"
    if download.move_files(destination):
        download.control_file_path.unlink()
        download.purge()

