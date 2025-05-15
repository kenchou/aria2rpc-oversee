#!/usr/bin/env python3
# ~/callbacks.py
import shutil

import aria2p
import click
import logging
import subprocess

from pathlib import Path

from aria2rpc import (
    load_aria2_config,
    LOG_LEVELS,
    DEFAULT_ARIA2_CONFIG,
    DEFAULT_ARIA2_HOST,
    DEFAULT_ARIA2_PORT,
)


LOG_FORMAT = "%(asctime)-15s [%(levelname)s] %(message)s"
logger = logging.getLogger()


def on_download_error(api, gid):
    # pop a desktop notification using notify-send
    download = api.get_download(gid)
    summary = f"A download failed"
    body = f"{download.name}\n{download.error_message} (code: {download.error_code})."
    subprocess.call(["notify-send", "-t", "10000", summary, body])


def print_task_info(task):
    print(f"+ {task.name}")
    print(f"  - {task.error_code=}, {task.error_message}")
    print(f"  - {task.dir}")
    print(
        f"  - {task.gid:<17} "
        f"{task.status:<9} "
        f"{task.progress_string():>8} "
        f"{task.download_speed_string():>12} "
        f"{task.upload_speed_string():>12} "
        f"{task.eta_string():>8}"
    )


def on_download_complete(api, gid):
    task: aria2p.downloads.Download
    task = api.get_download(gid)
    print_task_info(task)
    # purge magnet metadata task
    if task.is_metadata:
        logger.info(f'Purge Complete metadata {task.gid}: "{task.name}".')
        task.purge()
        return
    # move files from tmp dir to another
    if ".tmp" == task.dir.name:
        subprocess.call(["chmod", "-R", "g+w", Path(task.dir)])
        destination = Path(task.dir.parent)
        logger.info(
            f'Task {task.gid} Complete: move "{task.name}" from {task.dir} to {destination}'
        )
        if move_or_merge(task, destination):
            control_file = task.control_file_path
            if control_file.exists():
                logger.info(f"Remove control file: {control_file}")
                control_file.unlink()
            # do not purge bt task
            # task.purge()


def move_or_merge(task: aria2p.downloads.Download, destination: Path) -> bool:
    all_success = True
    if destination.exists():  # 目标已存在，使用 rsync
        logger.info(f"Sync {task.root_files_paths=} to {destination}")
        for path in task.root_files_paths:
            # rsync 同步，然后删除源文件（移动，但保留空目录）
            result = subprocess.run(
                ["/usr/bin/rsync", "-a", "--remove-source-files", "--progress", path, destination],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            exit_code = result.returncode
            stdout_output = result.stdout
            stderr_output = result.stderr

            logger.debug(f"--> rsync -a {path} {destination}")
            logger.debug(f"{exit_code=}")
            logger.debug(f"{stdout_output=}")
            logger.debug(f"{stderr_output=}")

            if exit_code == 0:
                if path.is_dir():   # 删除目录树
                    logger.info(f"--> rm -rf {path}")
                    shutil.rmtree(path, ignore_errors=True)
                else:   # 删除文件
                    logger.info(f"--> rm {path}")
                    path.unlink(missing_ok=True)
            else:
                logger.info(f"--> rsync failed. exit code: {exit_code}")
                all_success = False
        return all_success
    else:
        logger.info(f"move {task.root_files_paths=} to {destination}")
        return task.move_files(destination)


@click.command()
@click.argument("gid")
@click.argument("file-count")
@click.argument("destination")
@click.option(
    "--config-file",
    default=DEFAULT_ARIA2_CONFIG,
    type=click.Path(),
    help="config of Aria2 JSON-RPC server. "
    "if provide both --config-file and --json-rpc/--token, prefers to use --json-rpc/--token",
    show_default=True,
)
@click.option(
    "--host", help="Aria2 JSON-RPC server host. default: {}".format(DEFAULT_ARIA2_HOST)
)
@click.option(
    "--port", help="Aria2 JSON-RPC server port. default: {}".format(DEFAULT_ARIA2_PORT)
)
@click.option("--token", help="RPC SECRET string")
def cli(gid, file_count, destination, config_file, host, port, token):
    logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

    fh = logging.FileHandler("/tmp/aria2-event.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(fh)

    logger.info(f'Arguments: {gid} {file_count} "{destination}"')

    config = load_aria2_config(config_file)
    logger.debug(config)

    on_download_complete(
        aria2p.API(
            aria2p.Client(
                host=host or config.get("host"),
                port=port or config.get("port"),
                secret=token or config.get("token"),
            )
        ),
        gid,
    )


if __name__ == "__main__":
    cli()
