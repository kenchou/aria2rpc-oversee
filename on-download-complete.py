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
    task = api.get_download(gid)
    print_task_info(task)
    summary = f"A download failed"
    body = f"{task.name}\n{task.error_message} (code: {task.error_code})."
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
        logger.info(f'[{gid}] Purge Complete metadata {task.gid}: "{task.name}".')
        task.purge()
        return
    # move files from tmp dir to another
    if ".tmp" == task.dir.name:
        subprocess.call(["chmod", "-R", "g+w", Path(task.dir)])
        destination = Path(task.dir.parent)
        logger.info(
            f'[{gid}] Task Completed: move "{task.name}" from {task.dir} to {destination}'
        )
        if move_or_merge(task, destination):
            control_file = task.control_file_path
            if control_file.exists():
                logger.info(f"[{gid}] Remove control file: {control_file}")
                control_file.unlink()
            # do not purge bt task
            # task.purge()


def move_or_merge(task: aria2p.downloads.Download, destination: Path) -> bool:
    all_success = True
    task_id = task.gid

    # 检查是否有冲突（目标位置已存在同名文件/目录）
    has_conflicts = False
    logger.debug(
        f"[{task_id}] Checking conflicts for {len(task.root_files_paths)} paths"
    )
    logger.debug(f"[{task_id}] task.dir = {task.dir}")
    logger.debug(f"[{task_id}] destination = {destination}")

    for path in task.root_files_paths:
        logger.debug(f"[{task_id}] Checking path: {path}")

        # 获取相对于下载目录的根级别名称
        try:
            relative_path = path.relative_to(task.dir)
            root_name = relative_path.parts[0]  # 取第一部分作为根级别名称
            logger.debug(
                f"[{task_id}] relative_path = {relative_path}, root_name = {root_name}"
            )
        except (ValueError, IndexError) as e:
            # 如果无法获取相对路径，直接使用文件名
            root_name = path.name
            logger.debug(
                f"[{task_id}] Exception getting relative path: {e}, using path.name = {root_name}"
            )

        target_path = destination / root_name
        logger.debug(f"[{task_id}] Checking if target_path exists: {target_path}")

        if target_path.exists():
            logger.info(
                f"[{task_id}] Conflict detected: {target_path} already exists (is_file={target_path.is_file()}, is_dir={target_path.is_dir()})"
            )
            has_conflicts = True
            break
        else:
            logger.debug(f"[{task_id}] No conflict: {target_path} does not exist")

    # 如果没有冲突，直接使用 move_files（最高效）
    if not has_conflicts:
        logger.info(
            f"[{task_id}] No conflicts detected, using move_files to {destination}"
        )
        return task.move_files(destination)

    # 有冲突时，使用 rsync 处理每个文件/目录
    logger.info(f"[{task_id}] Conflicts detected, using rsync for merge")
    for path in task.root_files_paths:
        # rsync 同步，然后删除源文件（移动，但保留空目录）
        result = subprocess.run(
            [
                "/usr/bin/rsync",
                "-hav",
                "--partial",
                "--remove-source-files",
                path,
                destination,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        exit_code = result.returncode
        stdout_output = result.stdout
        stderr_output = result.stderr

        logger.debug(
            f"[{task_id}] --> rsync -hav --partial --remove-source-files {path} {destination}"
        )
        for line in stdout_output.splitlines():
            logger.debug(f"[{task_id}] {line}")
        for line in stderr_output.splitlines():
            logger.debug(f"[{task_id}] {line}")
        logger.debug(f"[{task_id}] {exit_code=}")

        if exit_code == 0:
            if path.is_dir():  # 删除目录树
                logger.info(f"[{task_id}] --> rm -rf {path}")
                shutil.rmtree(path, ignore_errors=True)
            else:  # 删除文件
                logger.info(f"[{task_id}] --> rm {path}")
                path.unlink(missing_ok=True)
        else:
            logger.info(f"[{task_id}] --> rsync failed. exit code: {exit_code}")
            all_success = False

    return all_success


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

    logger.info(f'[{gid}] Arguments: {gid=} {file_count=} destination="{destination}"')

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
