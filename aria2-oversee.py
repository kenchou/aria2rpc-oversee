#!/usr/bin/env python3

import click
import click_log
import logging

from pathlib import Path
from time import sleep

from aria2rpc import Aria2RpcClient, Aria2QueueManager, \
    print_response_status, get_config, guess_path, \
    LOG_LEVELS, DEFAULT_CONFIG_PATH, DEFAULT_ARIA2_CONFIG, DEFAULT_ARIA2_JSONRPC


@click.command()
@click.option('--config-file', default=DEFAULT_ARIA2_CONFIG, type=click.Path(),
              help=f'config of Aria2 JSON-RPC server. '
                   'if provide both --config-file and --json-rpc/--token, prefers to use --json-rpc/--token',
              show_default=True)
@click.option('--json-rpc', help='Aria2 JSON-RPC server. default: {}'.format(DEFAULT_ARIA2_JSONRPC))
@click.option('--token', help='RPC SECRET string')
@click.option('-v', '--verbose', count=True, help='Increase output verbosity.')
def run(config_file, json_rpc, token, verbose):
    logging.basicConfig(level=LOG_LEVELS.get(verbose, logging.INFO))
    logger = logging.getLogger(__name__)
    click_log.basic_config(logger)

    guess_paths = [
        Path.home() / DEFAULT_CONFIG_PATH,  # ~/.aria2/
        Path(__file__).resolve().parent / DEFAULT_CONFIG_PATH,  # ${BIN_PATH}/.aria2/
    ]
    config_file_path = guess_path(config_file, guess_paths) or guess_path(DEFAULT_ARIA2_CONFIG, guess_paths)
    config = get_config(config_file_path)

    if not json_rpc:
        json_rpc = config.get('json-rpc', DEFAULT_ARIA2_JSONRPC)
    if not token:
        token = config.get('token')

    aria2 = Aria2RpcClient(url=json_rpc, token=token)
    aria2_queue_manager = Aria2QueueManager(aria2)

    while True:
        # has waiting tasks?
        waiting = aria2.tellWaiting(0, 1)
        if True or len(waiting.result):
            response = aria2.tellActive()
            print_response_status(response)
            if not response.error:
                aria2_queue_manager.update(response.result)
            waiting = aria2.tellWaiting(0, 20)
            print_response_status(waiting, title='### Waiting ###')
        else:
            logger.info('No waiting tasks in queue.')
        logger.info('sleep 300s.')
        sleep(300)


if __name__ == "__main__":
    run()
