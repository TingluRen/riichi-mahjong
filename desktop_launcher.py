"""Local, offline launcher. Build the Windows executable with build_exe.ps1."""
import argparse
from contextlib import contextmanager
import logging
import os
from pathlib import Path
import socket
import sys
import threading
import webbrowser


def user_data_dir():
    override = os.environ.get('MAHJONG_DESKTOP_HOME')
    if override:
        return Path(override).expanduser().resolve()
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'TingluRen' / 'RiichiMahjong'
    return Path.home() / '.local' / 'share' / 'tingluren-riichi-mahjong'


@contextmanager
def single_instance(directory):
    """An OS-owned lock is released even if the program is terminated."""
    with (directory / 'launcher.lock').open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('Riichi Mahjong is already running. Use the existing launcher window.') from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def run(port=0, open_browser=True):
    directory = user_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    with single_instance(directory):
        # Set before importing server; never write inside a one-file extraction folder.
        os.environ['MAHJONG_SAVE_PATH'] = str(directory / 'saved_game.json')
        logging.basicConfig(level=logging.INFO, handlers=[
            logging.FileHandler(directory / 'launcher.log', encoding='utf-8'),
            logging.StreamHandler(),
        ])
        import uvicorn
        import server
        application = server.app
        if not any(getattr(route, 'path', '') == '/health' for route in application.routes):
            @application.get('/health')
            def health():
                return {'status': 'ok'}

        # Reserve the actual socket, avoiding a check-then-bind race and busy ports.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', port))
            listener.listen(128)
            url = f'http://127.0.0.1:{listener.getsockname()[1]}'
            engine = uvicorn.Server(uvicorn.Config(
                application, host='127.0.0.1', port=listener.getsockname()[1],
                workers=1, loop='asyncio', http='h11', ws='none',
                access_log=False, log_config=None,
            ))
            stop = threading.Event()

            def announce():
                while not stop.wait(0.1):
                    if engine.started:
                        print(f'Game ready: {url}', flush=True)
                        print(f'Saves: {directory}', flush=True)
                        print('Keep this window open while playing. Press Ctrl+C here to quit.', flush=True)
                        if open_browser:
                            try:
                                if not webbrowser.open(url):
                                    print('Open the game address above in your browser.', flush=True)
                            except Exception:
                                logging.exception('Could not open browser; use the printed address.')
                        return

            browser_thread = threading.Thread(target=announce, daemon=True)
            browser_thread.start()
            try:
                engine.run(sockets=[listener])
            finally:
                stop.set()
                browser_thread.join(timeout=2)
            if not engine.started:
                raise RuntimeError('The local server could not start. See launcher.log in the save folder.')


def main():
    parser = argparse.ArgumentParser(description='Launch offline Riichi Mahjong in your browser.')
    parser.add_argument('--no-browser', action='store_true', help='Print the local URL without opening a browser.')
    parser.add_argument('--port', type=int, default=0, help='Local port; 0 automatically selects an available port.')
    args = parser.parse_args()
    try:
        run(args.port, not args.no_browser)
    except Exception as error:
        logging.exception('Launcher failed')
        print(f'Could not start Riichi Mahjong: {error}', file=sys.stderr, flush=True)
        if os.name == 'nt' and sys.stdin.isatty():
            input('Press Enter to close...')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
