#!/usr/bin/env python3

import base64
import click
import click_log
import logging
import re

from pathlib import Path
from fnmatch import fnmatch
from torrent_parser import TorrentFileParser, InvalidTorrentDataException

from aria2rpc import Aria2RpcClient, print_status, get_config, guess_path, \
    DEFAULT_CONFIG_PATH, DEFAULT_ARIA2_CONFIG, DEFAULT_ARIA2_JSONRPC, DEFAULT_TORRENT_EXCLUDE_LIST_FILE


PATTERN_SUPPORTED_URI = re.compile('(http(s)?|ftp(s)|sftp)://|magnet:')


def is_supported_uri(uri):
    return PATTERN_SUPPORTED_URI.match(uri)


def is_torrent_file(filename):
    return '.torrent' == Path(filename).suffix


def is_aria2_file(filename):
    return '.aria2' == Path(filename).suffix


def torrent_filter_file(torrent_info, excludes):
    if 'files' not in torrent_info:  # filter if there is multi-files torrent
        return False
    selected = []
    for idx, file_info in enumerate(torrent_info['files'], 1):
        include_path = len(file_info['path']) > 1
        file_path = Path().joinpath(*file_info['path'])
        file_length = file_info["length"]
        _lower_file_path = file_path.lower()  # for fnmatch case-insensitive
        for p in excludes:
            exclude_pattern = Path('*') / p if include_path else p
            if fnmatch(_lower_file_path, exclude_pattern.lower()):
                logging.debug(f'{torrent_info["name"]}, match: {exclude_pattern}, '
                              f'skip file: "{file_path}", len: {file_length}')
                break
        else:
            logging.info(f'{torrent_info["name"]}, selected {idx}, file: "{file_path}", len: {file_length}')
            selected.append(str(idx))
    return selected


def build_exclude_list(filename):
    exclude_patterns = []
    if filename:
        with open(filename) as f:
            for line in f:
                line = line.strip()
                if not line or '#' == line[1]:  # skip empty lines or comment
                    continue
                exclude_patterns.append(line)
    return exclude_patterns


@click.group()
@click.option('--config-file', default=DEFAULT_ARIA2_CONFIG,
              help=f'config of Aria2 JSON-RPC server. '
                   'if provide both --conf and --json-rpc/--token, prefers to use --json-rpc/--token',
              show_default=True)
@click.option('--json-rpc', help='Aria2 JSON-RPC server.')
@click.option('--token', help='RPC SECRET string.')
@click.option('--debug', is_flag=True, default=False, help="enable debug mode")
@click.pass_context
def cli(ctx, config_file, json_rpc, token, debug):
    """Aria2 RPC Client"""
    logging.basicConfig(level=logging.DEBUG if debug else logging.WARNING)
    # init logger
    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger(__name__)
    click_log.basic_config(logger)

    guess_paths = [
        Path.cwd(),  # current dir ./
        Path.home() / DEFAULT_CONFIG_PATH,    # ~/.aria2/
        Path(__file__).resolve().parent / DEFAULT_CONFIG_PATH,  # ${BIN_PATH}/.aria2/
    ]
    config_file_path = guess_path(config_file or DEFAULT_ARIA2_CONFIG, guess_paths)
    if config_file_path is None:
        config = {'json-rpc': DEFAULT_ARIA2_JSONRPC}
        if config_file:     # warning if provided the config_file option but not found
            click.secho(f'Warning: config {config_file} not found in paths: {guess_paths}, ', err=True, fg='yellow')
    else:
        config = get_config(config_file_path)

    if not json_rpc:
        json_rpc = config.get('json-rpc', DEFAULT_ARIA2_JSONRPC)
    if not token:
        token = config.get('token')

    ctx.ensure_object(dict)
    ctx.obj['json_rpc'] = json_rpc
    ctx.obj['token'] = token
    ctx.obj['config'] = config
    ctx.obj['guess_paths'] = guess_paths
    ctx.obj['aria2'] = Aria2RpcClient(json_rpc, token=token)


@cli.command()
@click.option('-d', '--download-dir', type=click.Path(exists=False), help="The directory to store the downloaded file.")
@click.option('-x', '--exclude-file', type=click.Path(exists=False), default='clean.lst',
              help="path to file of exclude list.", show_default=True)
@click.option('--pause', 'set_pause', is_flag=True, help='Pause download after added.')
@click.argument('torrent-files-or-uris', nargs=-1, required=True)
@click.pass_context
def add(ctx, download_dir, exclude_file, set_pause, torrent_files_or_uris):
    """Add tasks.

    Support: *.torrent, magnet://, http://, https://, ftp://, ftps://, sftp://
    """
    guess_paths = ctx.obj['guess_paths']
    aria2 = ctx.obj['aria2']

    click.echo('## Options:')
    click.echo(f'* download-dir: {download_dir}')
    click.echo(f'*      exclude: {exclude_file}')
    click.echo(f'*        pause: {set_pause}')
    click.echo(f'*        files: {torrent_files_or_uris}')

    exclude_file_path = guess_path(exclude_file, guess_paths) or guess_path(DEFAULT_TORRENT_EXCLUDE_LIST_FILE, guess_paths)
    # exclude list
    exclude_patterns = build_exclude_list(exclude_file_path)

    options = {}
    if download_dir:
        options['dir'] = str(Path(download_dir))
    if set_pause:
        options['pause'] = 'true' if set_pause else 'false'

    for uri in torrent_files_or_uris:
        click.echo(f'## process {uri}')
        if is_supported_uri(uri):
            # aria2.addUri([secret, ]uris[, options[, position]])
            # @see https://aria2.github.io/manual/en/html/aria2c.html#aria2.addUri
            response = aria2.addUri([uri], options)
            click.echo(response)
            pass
        elif is_torrent_file(uri):
            try:
                with open(uri, 'rb') as f:
                    # parse torrent file
                    torrent = TorrentFileParser(f).parse()
                    selected = torrent_filter_file(torrent['info'], exclude_patterns)
                    if selected:
                        options['select-file'] = ','.join(selected)
                    f.seek(0)   # rewind the file
                    # aria2.addTorrent([secret, ]torrent[, uris[, options[, position]]])
                    # @see https://aria2.github.io/manual/en/html/aria2c.html#aria2.addTorrent
                    response = aria2.addTorrent(base64.b64encode(f.read()).decode('utf-8'), [], options)
                    click.echo(response)
            except InvalidTorrentDataException as e:
                click.secho(f'skip torrent file: "{uri}", reason: {e}', err=True, fg='yellow')
                continue
        elif is_aria2_file(uri):
            # TODO: parse .aria2 file and add magnet URI
            click.secho(f'Not currently supported file "{uri}"', err=True, fg='red')
        else:
            click.secho(f'Unknown file "{uri}"', err=True, fg='red')


@cli.command(name='list')
@click.option('-a', '--all', 'show_all', is_flag=True, default=False, help="display all status. same as -t -w -c")
@click.option('-t', '--active', 'show_active', is_flag=True, default=False, help="display active queue.")
@click.option('-w', '--waiting', 'show_waiting', is_flag=True, default=False, help="display waiting queue.")
@click.option('-s', '--stopped', 'show_stopped', is_flag=True, default=False, help="display complete/stopped tasks.")
@click.pass_context
def list_queue(ctx, show_all, show_active, show_waiting, show_stopped):
    """Show status of tasks"""
    aria2 = ctx.obj['aria2']

    show_active = show_active or not (show_waiting or show_stopped)
    if show_all or show_active:
        response = aria2.tellActive()
        print_status(response, title='### Active ###')
    if show_all or show_waiting:
        response = aria2.tellWaiting(0, 50)
        print_status(response, title='### Waiting ###')
    if show_all or show_stopped:
        response = aria2.tellStopped(0, 50)
        print_status(response, title='### Completed/Stopped ###')


@cli.command()
@click.pass_context
def show(ctx):
    """TODO: Show detail info of a task"""


@cli.command()
@click.pass_context
def remove(ctx):
    """TODO: Remove a task."""


@cli.command()
@click.pass_context
def pause(ctx):
    """TODO: pause a task"""


@cli.command()
@click.pass_context
def pause_all(ctx):
    """Pause all tasks"""
    aria2 = ctx.obj['aria2']
    response = aria2.pauseAll()
    click.echo(response)


@cli.command()
@click.pass_context
def unpause_all(ctx):
    """Unpause all tasks"""
    aria2 = ctx.obj['aria2']
    response = aria2.unpauseAll()
    click.echo(response)


@cli.command()
@click.pass_context
def purge(ctx):
    """Purges completed/error/removed downloads to free memory"""
    aria2 = ctx.obj['aria2']
    response = aria2.purgeDownloadResult()
    click.echo(response)


@cli.command()
@click.pass_context
def set_priority(ctx):
    """TODO: Change the position of a task"""


@cli.command()
@click.pass_context
def save_session(ctx):
    """Save the current session to file (specified by the --save-session option)"""
    aria2 = ctx.obj['aria2']
    response = aria2.saveSession()
    click.echo(response)


@cli.command()
@click.pass_context
def shutdown(ctx):
    """TODO: shut down aria2"""


@cli.command()
@click.pass_context
def ui(ctx):
    pass


if __name__ == '__main__':
    cli()
