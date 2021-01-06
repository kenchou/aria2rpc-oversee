#!/usr/bin/env python3
# ~/callbacks.py

import aria2p
import click
import logging
import subprocess

from pathlib import Path

from aria2rpc import load_aria2_config, \
    LOG_LEVELS, DEFAULT_ARIA2_CONFIG, DEFAULT_ARIA2_HOST, DEFAULT_ARIA2_PORT


LOG_FORMAT = '%(asctime)-15s [%(levelname)s] %(message)s'
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
    print(f"  - {task.gid:<17} "
          f"{task.status:<9} "
          f"{task.progress_string():>8} "
          f"{task.download_speed_string():>12} "
          f"{task.upload_speed_string():>12} "
          f"{task.eta_string():>8}")


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
    if '.tmp' == task.dir.name:
        destination = Path(task.dir.parent)
        logger.info(f'Complete {task.gid}: move "{task.name}" from {task.dir} to {destination}')
        if task.move_files(destination):
            control_file = task.control_file_path
            if control_file.exists():
                control_file.unlink()
            # do not purge bt task
            # task.purge()


@click.command()
@click.argument('gid')
@click.argument('file-count')
@click.argument('destination')
@click.option('--config-file', default=DEFAULT_ARIA2_CONFIG, type=click.Path(),
              help='config of Aria2 JSON-RPC server. '
                   'if provide both --config-file and --json-rpc/--token, prefers to use --json-rpc/--token',
              show_default=True)
@click.option('--host', help='Aria2 JSON-RPC server host. default: {}'.format(DEFAULT_ARIA2_HOST))
@click.option('--port', help='Aria2 JSON-RPC server port. default: {}'.format(DEFAULT_ARIA2_PORT))
@click.option('--token', help='RPC SECRET string')
@click.option('-v', '--verbose', count=True, help='Increase output verbosity.')
def cli(gid, file_count, destination, config_file, host, port, token, verbose):
    logging.basicConfig(level=LOG_LEVELS.get(verbose, logging.INFO), format=LOG_FORMAT)

    fh = logging.FileHandler('/tmp/aria2-event.log')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(fh)

    logger.info(f'{gid}, {file_count}, "{destination}"')

    config = load_aria2_config(config_file)
    on_download_complete(
        aria2p.API(
            aria2p.Client(
                host=host or config.get('host'),
                port=port or config.get('port'),
                secret=token or config.get('token')
            )
        ),
        gid
    )


if __name__ == '__main__':
    cli()
