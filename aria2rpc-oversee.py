#!/usr/bin/env python3

import aria2p
import click
import click_log
import logging
import requests.exceptions
import signal

from pathlib import Path
from threading import Event

from aria2rpc import Aria2QueueManager, \
    get_config, guess_path, \
    LOG_LEVELS, DEFAULT_CONFIG_PATH, DEFAULT_ARIA2_CONFIG, DEFAULT_ARIA2_HOST, DEFAULT_ARIA2_PORT


LOG_FORMAT = '%(asctime)-15s [%(levelname)s] %(message)s'
exit_event = Event()


def register_single():
    def sigint_handler(sig, frame):
        exit_event.set()
        print('You pressed Ctrl+C! Wait for exit.')

    # register single handler
    for sig in ('TERM', 'HUP', 'INT'):
        signal.signal(getattr(signal, 'SIG' + sig), sigint_handler)


@click.command()
@click.option('--config-file', default=DEFAULT_ARIA2_CONFIG, type=click.Path(),
              help='config of Aria2 JSON-RPC server. '
                   'if provide both --config-file and --json-rpc/--token, prefers to use --json-rpc/--token',
              show_default=True)
@click.option('--host', help='Aria2 JSON-RPC server host. default: {}'.format(DEFAULT_ARIA2_HOST))
@click.option('--port', help='Aria2 JSON-RPC server port. default: {}'.format(DEFAULT_ARIA2_PORT))
@click.option('--token', help='RPC SECRET string')
@click.option('-t', '--interval', default=300, help='Check interval')
@click.option('-v', '--verbose', count=True, help='Increase output verbosity.')
def run(config_file, host, port, token, interval, verbose):
    max_level = max(LOG_LEVELS, key=int)
    logging.basicConfig(level=LOG_LEVELS.get(min(verbose, max_level), logging.INFO), format=LOG_FORMAT)
    logger = logging.getLogger(__name__)
    logger.setLevel(LOG_LEVELS.get(min(verbose, max_level), logging.INFO))
    click_log.basic_config(logger)

    guess_paths = [
        Path.home() / DEFAULT_CONFIG_PATH,  # ~/.aria2/
        Path(__file__).resolve().parent / DEFAULT_CONFIG_PATH,  # ${BIN_PATH}/.aria2/
    ]
    config_file_path = guess_path(config_file, guess_paths) or guess_path(DEFAULT_ARIA2_CONFIG, guess_paths)
    config = get_config(config_file_path)

    aria2 = aria2p.API(
        aria2p.Client(
            host=host or config.get('host', DEFAULT_ARIA2_HOST),
            port=port or config.get('port', DEFAULT_ARIA2_PORT),
            secret=token or config.get('token')
        )
    )

    register_single()

    aria2_queue_manager = Aria2QueueManager(aria2)

    logging.debug('Main loop.')
    while not exit_event.is_set():
        try:
            aria2_queue_manager.run()
        except requests.exceptions.ConnectTimeout as e:
            logging.warning('Connect Timeout: %s', str(e))
        logger.info(f'sleep {interval}s.')
        exit_event.wait(interval)
    click.secho('Program exit.', fg='green')


if __name__ == "__main__":
    run()
