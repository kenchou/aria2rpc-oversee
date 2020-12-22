#!/usr/bin/env python3

import aria2p
import base64
import click
import click_log
import logging
import re

from pathlib import Path
from fnmatch import fnmatch
from torrent_parser import TorrentFileParser, InvalidTorrentDataException

from aria2rpc import get_config, guess_path, \
    LOG_LEVELS, DEFAULT_CONFIG_PATH, DEFAULT_TORRENT_EXCLUDE_LIST_FILE, \
    DEFAULT_ARIA2_CONFIG, DEFAULT_ARIA2_HOST, DEFAULT_ARIA2_PORT


PATTERN_SUPPORTED_URI = re.compile('(http(s)?|ftp(s)|sftp)://|magnet:')
PATTERN_MAGNET_URI = re.compile('magnet:')


def is_supported_uri(uri):
    return PATTERN_SUPPORTED_URI.match(uri)


def is_magnet(uri):
    return PATTERN_MAGNET_URI.match(uri)


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
        _lower_file_path = str(file_path).lower()  # for fnmatch case-insensitive
        for p in excludes:
            exclude_pattern = str(Path('*') / p) if include_path else p
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
@click.option('--config-file', type=click.Path(exists=False),
              help=f'config of Aria2 JSON-RPC server. '
                   'if provide both --config-file and --json-rpc/--token, prefers to use --json-rpc/--token',
              show_default=True)
@click.option('--host', help='Aria2 JSON-RPC server host.')
@click.option('--port', help='Aria2 JSON-RPC server port.')
@click.option('--token', help='RPC SECRET string.')
@click.option('-v', '--verbose', count=True, help='Increase output verbosity.')
@click.pass_context
def cli(ctx, config_file, host, port, token, verbose):
    """Aria2 RPC Client"""
    logging.basicConfig(level=LOG_LEVELS.get(verbose, logging.INFO))
    # init logger
    logger = logging.getLogger(__name__)
    click_log.basic_config(logger)

    guess_paths = [
        Path('.'),  # current dir ./
        Path.home() / DEFAULT_CONFIG_PATH,  # ~/.aria2/
        Path(__file__).resolve().parent / DEFAULT_CONFIG_PATH,  # ${BIN_PATH}/.aria2/
    ]
    if config_file is not None:
        config_file_path = guess_path(config_file, guess_paths)
        if config_file_path is None:
            logger.error(f'--config-file "{config_file}" not found in paths: {[str(p) for p in guess_paths]}')
            exit(1)
    else:
        config_file_path = guess_path(DEFAULT_ARIA2_CONFIG, guess_paths)
    config = get_config(config_file_path) or {'host': DEFAULT_ARIA2_HOST, 'port': DEFAULT_ARIA2_PORT}

    ctx.ensure_object(dict)
    ctx.obj['host'] = host
    ctx.obj['port'] = port
    ctx.obj['token'] = token
    ctx.obj['config'] = config
    ctx.obj['guess_paths'] = guess_paths
    ctx.obj['aria2'] = aria2p.API(
        aria2p.Client(
            host=host or config.get('host', DEFAULT_ARIA2_HOST),
            port=port or config.get('port', DEFAULT_ARIA2_PORT),
            secret=token or config.get('token')
        )
    )
    ctx.obj['logger'] = logger


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
    logger = ctx.obj['logger']

    logger.info(f'* download-dir: {download_dir}')
    logger.info(f'* exclude: {exclude_file}')
    logger.info(f'* pause: {str(set_pause).lower()}')
    logger.info(f'* files: {torrent_files_or_uris}')

    exclude_file_path = guess_path(exclude_file, guess_paths) or guess_path(DEFAULT_TORRENT_EXCLUDE_LIST_FILE,
                                                                            guess_paths)
    # exclude list
    exclude_patterns = build_exclude_list(exclude_file_path)

    for uri in torrent_files_or_uris:
        logger.info(f'Add task {uri}')
        options = {}    # init option
        if download_dir:
            options['dir'] = str(Path(download_dir))
        if set_pause:
            options['pause'] = str(set_pause).lower()

        # TODO: check task in queue
        if is_supported_uri(uri):
            if is_magnet(uri):
                options['dir'] = str(Path(options.get('dir', '')) / '.tmp')
            # aria2.addUri([secret, ]uris[, options[, position]])
            # @see https://aria2.github.io/manual/en/html/aria2c.html#aria2.addUri
            response = aria2.add_uris([uri], options)
            click.echo(response)
            pass
        elif is_torrent_file(uri):
            options['dir'] = str(Path(options.get('dir', '')) / '.tmp')
            try:
                # setup option.select-file
                with open(uri, 'rb') as f:
                    # parse torrent file
                    torrent = TorrentFileParser(f).parse()
                    selected = torrent_filter_file(torrent['info'], exclude_patterns)
                    if selected:
                        options['select-file'] = ','.join(selected)
                    f.seek(0)  # rewind the file
                # aria2.addTorrent([secret, ]torrent[, uris[, options[, position]]])
                # @see https://aria2.github.io/manual/en/html/aria2c.html#aria2.addTorrent
                response = aria2.add_torrent(uri, [], options)
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
@click.option('-a', '--all', 'show_all', is_flag=True, default=False, help="display all status. same as -t -w -s")
@click.option('-t', '--active', 'show_active', is_flag=True, default=False, help="display active queue.")
@click.option('-w', '--waiting', 'show_waiting', is_flag=True, default=False, help="display waiting queue.")
@click.option('-p', '--paused', 'show_paused', is_flag=True, default=False, help="display paused queue.")
@click.option('-s', '--stopped', 'show_stopped', is_flag=True, default=False, help="display complete/stopped tasks.")
@click.pass_context
def list_queue(ctx, show_all, show_active, show_waiting, show_paused, show_stopped):
    """Show status of tasks"""
    aria2 = ctx.obj['aria2']

    show_active = show_active or not (show_waiting or show_stopped)
    for download in aria2.get_downloads():
        if show_all \
                or (show_active and download.is_active) \
                or (show_waiting and download.is_waiting) \
                or (show_paused and download.is_paused) \
                or (show_stopped and download.is_complete):
            print(
                f"{download.gid:<17} "
                f"{download.status:<9} "
                f"{download.progress_string():>8} "
                f"{download.download_speed_string():>12} "
                f"{download.upload_speed_string():>12} "
                f"{download.eta_string():>8}  "
                f"{download.name}"
            )


@cli.command()
@click.argument('gid', nargs=-1, required=True)
@click.pass_context
def info(ctx, gid):
    """Show detail info of a task"""
    gid_list = gid
    aria2 = ctx.obj['aria2']
    for gid in gid_list:
        download = aria2.get_download(gid)
        print(
            f"{download.gid:<17} "
            f"{download.status:<9} "
            f"{download.progress_string():>8} "
            f"{download.download_speed_string():>12} "
            f"{download.upload_speed_string():>12} "
            f"{download.eta_string():>8}  "
            f"{download.name}"
        )


@cli.command()
@click.argument('gids', nargs=-1)
@click.pass_context
def remove(ctx, gids):
    """TODO: Remove a task."""
    aria2 = ctx.obj['aria2']
    downloads = [aria2.get_download(gid) for gid in gids]
    response = aria2.remove(downloads)
    for r in response:
        if isinstance(r, aria2p.client.ClientException):
            print(f'{r=} {r.message}')
        else:
            print(f'{r=}')


@cli.command()
@click.argument('gids', nargs=-1)
@click.pass_context
def pause(ctx, gids):
    """Pause a running/waiting tasks"""
    aria2 = ctx.obj['aria2']
    downloads = [aria2.get_download(gid) for gid in gids]
    response = aria2.pause(downloads)
    for r in response:
        if isinstance(r, aria2p.client.ClientException):
            print(f'{r=} {r.message}')
        else:
            print(f'{r=}')
    for download in downloads:
        print(f'{download.gid=}, {download.status=}, {download.live.status=}, {download.status=}')


@cli.command()
@click.pass_context
def pause_all(ctx):
    """Pause all tasks"""
    aria2 = ctx.obj['aria2']
    response = aria2.pause_all()
    click.echo(response)


@cli.command()
@click.argument('gids', nargs=-1)
@click.pass_context
def resume(ctx, gids):
    """Resume paused tasks"""
    aria2 = ctx.obj['aria2']
    downloads = [aria2.get_download(gid) for gid in gids]
    response = aria2.resume(downloads)
    for r in response:
        if isinstance(r, aria2p.client.ClientException):
            print(f'{r=} {r.message}')
        else:
            print(f'{r=}')
    for download in downloads:
        print(f'{download.gid=}, {download.status=}, {download.live.status=}, {download.status=}')


@cli.command()
@click.pass_context
def resume_all(ctx):
    """Resume all paused tasks"""
    aria2 = ctx.obj['aria2']
    response = aria2.resume_all()
    click.echo(response)


@cli.command()
@click.pass_context
def purge(ctx):
    """Purges completed/error/removed downloads to free memory"""
    aria2 = ctx.obj['aria2']
    response = aria2.autopurge()
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
    response = aria2.client.save_session()
    click.echo(response)


@cli.command()
@click.pass_context
def shutdown(ctx):
    """TODO: shut down aria2"""


@cli.command()
@click.pass_context
def top(ctx):
    """
    Top subcommand.

    Parameters:
        ctx: dict

    Returns:
        int: always 0.
    """
    try:
        from aria2p.interface import Interface
    except ImportError:
        Interface = None
    if Interface is None:
        click.secho(
            "The top-interface dependencies are not installed. Try running `pip install aria2p[tui]` to install them.",
            fg='red',
            err=True,
        )
        return 1
    interface = Interface(ctx.obj['aria2'])
    success = interface.run()
    return 0 if success else 1


if __name__ == '__main__':
    cli()
