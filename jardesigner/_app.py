import os
import sys
import threading
import webbrowser
import argparse

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 5000


def _open_browser(host, port):
    import time
    time.sleep(1.5)
    webbrowser.open(f'http://{host}:{port}')


def main():
    parser = argparse.ArgumentParser(
        description='JARDesigner: Web GUI for MOOSE simulations'
    )
    parser.add_argument(
        '--port', type=int, default=DEFAULT_PORT,
        help=f'Port to run the server on (default: {DEFAULT_PORT})'
    )
    parser.add_argument(
        '--host', type=str, default=DEFAULT_HOST,
        help=f'Host address to bind to (default: {DEFAULT_HOST})'
    )
    parser.add_argument(
        '--no-browser', action='store_true',
        help='Start the server without opening the browser'
    )
    args = parser.parse_args()

    # Simulation subprocesses inherit this and use it to push results back
    # to this server. A wildcard bind address is reachable on loopback.
    internal_host = '127.0.0.1' if args.host in ('0.0.0.0', '::', '') else args.host
    os.environ['JARDESIGNER_SERVER_URL'] = f'http://{internal_host}:{args.port}'

    from jardesigner._server import app, socketio

    if not args.no_browser:
        browser_thread = threading.Thread(
            target=_open_browser,
            args=(args.host, args.port),
            daemon=True
        )
        browser_thread.start()

    print(f'JARDesigner is running at http://{args.host}:{args.port}')
    print('Press Ctrl+C to stop.')

    socketio.run(
        app,
        host=args.host,
        port=args.port,
        debug=False,
        use_reloader=False,
    )
