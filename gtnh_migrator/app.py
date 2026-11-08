"""Loopback-only web wizard. No account, uploads, telemetry, or hosted backend."""
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from . import search, world

WEB = Path(__file__).parent / 'web'


class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.info = self.plan = self.fit = self.result = None
        self.job = {'busy': False, 'kind': '', 'message': '', 'error': ''}

    def progress(self, message):
        with self.lock:
            self.job['message'] = message

    def launch(self, kind, operation):
        with self.lock:
            if self.job['busy']:
                raise ValueError('Another operation is still running')
            self.job = {'busy': True, 'kind': kind, 'message': 'Starting', 'error': ''}
        def work():
            try:
                operation()
            except Exception as exc:
                with self.lock:
                    self.job['error'] = str(exc)
            finally:
                with self.lock:
                    self.job['busy'] = False
        threading.Thread(target=work, daemon=True).start()

    def snapshot(self):
        with self.lock:
            return {'job': dict(self.job), 'info': self.info, 'plan': self.plan,
                    'fit': self.fit, 'result': self.result}


def handler(state, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, data, status=200, content_type='application/json; charset=utf-8'):
            raw = json.dumps(data, ensure_ascii=False).encode() if content_type.startswith('application/json') else data
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def allowed(self, auth=False):
            allowed_hosts = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in allowed_hosts:
                return False
            origin = self.headers.get('Origin')
            if origin and (urlparse(origin).netloc not in allowed_hosts or urlparse(origin).scheme != 'http'):
                return False
            return not auth or secrets.compare_digest(self.headers.get('X-Migration-Token', ''), token)

        def do_GET(self):
            if not self.allowed(self.path.startswith('/api/')):
                return self.reply({'error': 'Local access only'}, 403)
            if self.path == '/api/state':
                return self.reply(state.snapshot())
            if self.path == '/':
                return self.reply((WEB / 'index.html').read_bytes().replace(b'__TOKEN__', token.encode()),
                                  content_type='text/html; charset=utf-8')
            files = {'/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                     '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if self.path in files:
                name, mime = files[self.path]
                return self.reply((WEB / name).read_bytes(), content_type=mime)
            return self.reply({'error': 'Not found'}, 404)

        def do_POST(self):
            if not self.allowed(True):
                return self.reply({'error': 'Local access only'}, 403)
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 1024 * 1024:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(size))
                if self.path == '/api/browse':
                    path = Path(data.get('path') or Path.home()).expanduser().resolve()
                    if not path.is_dir():
                        path = path.parent
                    folders = []
                    for p in sorted(path.iterdir(), key=lambda p: p.name.casefold()):
                        if p.is_dir() and not p.is_symlink() and (not p.name.startswith('.') or p.name == '.minecraft'):
                            folders.append({'name': p.name, 'path': str(p)})
                    return self.reply({'path': str(path), 'parent': str(path.parent), 'folders': folders})
                if state.job['busy']:
                    raise ValueError('Wait for the current operation to finish')
                if self.path == '/api/inspect':
                    def inspect():
                        info = world.inspect(data['server'], data.get('client', ''))
                        with state.lock:
                            state.info = info
                            state.plan = state.fit = state.result = None
                    state.launch('inspect', inspect)
                elif self.path == '/api/plan':
                    if not state.info:
                        raise ValueError('Inspect a server first')
                    def plan():
                        state.progress('Reading original boundary terrain')
                        result = world.build_plan(state.info, data)
                        with state.lock:
                            state.plan = result
                            state.fit = state.result = None
                    state.launch('plan', plan)
                elif self.path == '/api/search':
                    if not state.plan:
                        raise ValueError('Prepare a preservation plan first')
                    def fit():
                        result = search.search(state.plan, state.progress)
                        with state.lock:
                            state.fit = result
                            state.plan['candidate'] = result['candidates'][0]
                    state.launch('search', fit)
                elif self.path == '/api/candidate':
                    index = int(data['index'])
                    if not state.fit or not 0 <= index < len(state.fit['candidates']):
                        raise ValueError('Unknown candidate')
                    state.plan['candidate'] = state.fit['candidates'][index]
                elif self.path == '/api/apply':
                    if data.get('stopped') is not True:
                        raise ValueError('Confirm that the source server and client are stopped')
                    if not state.plan:
                        raise ValueError('Prepare a plan first')
                    def apply():
                        result = world.apply(state.plan, data['target'], data.get('client_target', ''), state.progress)
                        with state.lock:
                            state.result = result
                    state.launch('apply', apply)
                else:
                    return self.reply({'error': 'Not found'}, 404)
                self.reply({'ok': True})
            except (ValueError, KeyError, OSError, TypeError) as exc:
                self.reply({'error': str(exc)}, 400)
    return Handler


def serve(port=0, open_browser=True):
    state = State()
    token = secrets.token_hex(32)
    server = ThreadingHTTPServer(('127.0.0.1', port), handler(state, token))
    server.daemon_threads = True
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'GTNH RWG2 Migrator: {url}\nYour data stays local. Keep this window open. Ctrl+C stops the wizard.', flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if state.job['busy']:
            print('Waiting for the current operation to finish safely…', flush=True)
            while state.job['busy']:
                threading.Event().wait(0.2)
    finally:
        server.server_close()
