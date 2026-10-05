import os
import sys
import socket
import threading
import webbrowser
import argparse

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 5000
# When --port is not given and DEFAULT_PORT is busy (e.g. macOS AirPlay
# Receiver listens on 5000), try this many following ports, as JupyterLab does.
PORT_RETRIES = 50


def _version():
    from importlib.metadata import version, PackageNotFoundError
    try:
        return version('jardesigner')
    except PackageNotFoundError:
        return 'unknown (not installed)'


def _open_browser(url):
    import time
    time.sleep(1.5)
    webbrowser.open(url)


def _check_moose():
    """Exit with an actionable message if the MOOSE simulator cannot load.

    The server itself starts without MOOSE, so without this check a broken
    install only shows up later as a failure inside every simulation.
    """
    try:
        import moose  # noqa: F401
    except ImportError as e:
        lines = [f'Error: the MOOSE simulator (pymoose) could not be loaded: {e}']
        if os.name == 'nt' and 'DLL load failed' in str(e):
            lines += [
                '',
                'The pymoose 5.0.0 Windows wheels on PyPI do not include the GSL',
                'and HDF5 libraries they need. Until a fixed pymoose is released,',
                'install jardesigner in a conda environment that provides them:',
                '',
                '    conda create -n jardesigner -c conda-forge python=3.12 gsl=2.8 hdf5=2.2.0',
                '    conda activate jardesigner',
                '    pip install jardesigner',
            ]
        sys.exit('\n'.join(lines))


def _port_is_free(host, port):
    family = socket.AF_INET6 if ':' in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as s:
        # Mirror gevent, which sets SO_REUSEADDR on POSIX only. On Windows
        # that option would let the probe bind a port that is in use.
        if os.name == 'posix':
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
        except OSError:
            return False
    return True


def _choose_port(host, requested):
    if requested is not None:
        if not _port_is_free(host, requested):
            sys.exit(f'Error: port {requested} on {host} is already in use. '
                     f'Choose another with --port.')
        return requested
    for port in range(DEFAULT_PORT, DEFAULT_PORT + PORT_RETRIES + 1):
        if _port_is_free(host, port):
            if port != DEFAULT_PORT:
                print(f'Port {DEFAULT_PORT} is in use, using port {port} instead.')
            return port
    sys.exit(f'Error: no free port found between {DEFAULT_PORT} and '
             f'{DEFAULT_PORT + PORT_RETRIES}. Choose one with --port.')


def main():
    parser = argparse.ArgumentParser(
        description='JARDesigner: Web GUI for MOOSE simulations'
    )
    parser.add_argument(
        '--port', type=int, default=None,
        help=f'Port to run the server on (default: {DEFAULT_PORT}, or the '
             f'next free port if that is in use)'
    )
    parser.add_argument(
        '--host', type=str, default=DEFAULT_HOST,
        help=f'Host address to bind to (default: {DEFAULT_HOST})'
    )
    parser.add_argument(
        '--no-browser', action='store_true',
        help='Start the server without opening the browser'
    )
    parser.add_argument(
        '--version', action='version', version=f'jardesigner {_version()}'
    )
    args = parser.parse_args()

    _check_moose()
    port = _choose_port(args.host, args.port)

    # A wildcard bind address is reachable on loopback; use that both for the
    # browser and for simulation subprocesses, which inherit
    # JARDESIGNER_SERVER_URL and push their results back to this server.
    local_host = '127.0.0.1' if args.host in ('0.0.0.0', '::', '') else args.host
    url_host = f'[{local_host}]' if ':' in local_host else local_host
    url = f'http://{url_host}:{port}'
    os.environ['JARDESIGNER_SERVER_URL'] = url

    from jardesigner._server import app, socketio

    if not args.no_browser:
        browser_thread = threading.Thread(
            target=_open_browser,
            args=(url,),
            daemon=True
        )
        browser_thread.start()

    print(f'JARDesigner is running at {url}')
    print('Press Ctrl+C to stop.')

    try:
        socketio.run(
            app,
            host=args.host,
            port=port,
            debug=False,
            use_reloader=False,
        )
    except KeyboardInterrupt:
        print('\nJARDesigner stopped.')
