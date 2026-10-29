"""relay.py: the only process in Brain Intake with a route off the internal network.

The app container sits on a Docker network marked internal, which has no route out: it cannot reach
the internet, the Mac, or anything else. This relay sits on that network and on one ordinary network,
and serves exactly two fixed routes:

  8765   page    a plain TCP forward to app:8765, published by Docker on the Mac's 127.0.0.1 only
  11434  ollama  an HTTP filter in front of Ollama on the Mac (host.docker.internal:11434)

The Ollama route is a filter, not a pipe, because Ollama's API can reach the internet on its own
(pull, push, cloud models) and can delete models. It passes three requests and nothing else:
  GET /api/tags, and POST /api/chat or /api/embed naming a model that is already installed on the Mac
  and runs there. Each request gets its own connection (Connection: close), so every one is checked.

Both routes keep one idle timer per connection, reset by traffic in either direction, and pass a
closed browser tab or app request on as a half-close, so the model stops when nobody is listening.
Standard library only.
"""
import asyncio, json, os, re, signal, sys, time

PAGE = ('app', 8765)
OLLAMA = ('host.docker.internal', 11434)
ALLOWED = {('GET', '/api/tags'), ('POST', '/api/chat'), ('POST', '/api/embed')}
MAX_BODY = 32 * 1048576
FIRST_BYTE = 30.0          # an idle preconnect is dropped after this
IDLE = {'page': 600.0, 'ollama': 900.0}
SLOTS = {'page': int(os.environ.get('RELAY_PAGE_CONNECTIONS', '64')), 'ollama': int(os.environ.get('RELAY_OLLAMA_CONNECTIONS', '16'))}
_models = {'at': 0.0, 'names': set()}


def log(*a): print('relay:', *a, flush=True)


async def bridge(a_reader, a_writer, b_reader, b_writer, idle):
    """Copy both directions. One idle timer for the pair; end of file on one side half-closes the other."""
    last = [time.monotonic()]

    async def pipe(r, w):
        try:
            while True:
                data = await r.read(65536)
                if not data: break
                last[0] = time.monotonic()
                w.write(data); await w.drain()
        except (ConnectionError, OSError, asyncio.CancelledError):
            pass
        finally:
            try:
                if w.can_write_eof(): w.write_eof()
            except (OSError, RuntimeError):
                pass

    tasks = [asyncio.ensure_future(pipe(a_reader, b_writer)), asyncio.ensure_future(pipe(b_reader, a_writer))]
    try:
        while not all(t.done() for t in tasks):
            await asyncio.wait(tasks, timeout=5, return_when=asyncio.ALL_COMPLETED)
            if time.monotonic() - last[0] > idle: break       # nothing either way for too long
    finally:
        for t in tasks: t.cancel()
        for w in (a_writer, b_writer):
            try: w.close()
            except OSError: pass


async def page(c_reader, c_writer, slots):
    if slots.locked(): c_writer.close(); return
    async with slots:
        try:
            first = await asyncio.wait_for(c_reader.read(65536), FIRST_BYTE)
        except (asyncio.TimeoutError, ConnectionError, OSError):
            c_writer.close(); return
        if not first: c_writer.close(); return
        try:
            u_reader, u_writer = await asyncio.wait_for(asyncio.open_connection(*PAGE), 10)
        except (OSError, asyncio.TimeoutError):
            c_writer.close(); return
        u_writer.write(first)
        await bridge(c_reader, c_writer, u_reader, u_writer, IDLE['page'])


def refuse(writer, status, reason):
    body = json.dumps({'error': f'relay: {reason}'}).encode()
    writer.write(f'HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n'
                 f'Connection: close\r\n\r\n'.encode() + body)
    log('refused', status, reason)


async def installed_models():
    """Models installed on the Mac and run there; cached for 30 s."""
    if time.monotonic() - _models['at'] < 30: return _models['names']
    r, w = await asyncio.wait_for(asyncio.open_connection(*OLLAMA), 5)
    try:
        w.write(b'GET /api/tags HTTP/1.1\r\nHost: localhost:11434\r\nConnection: close\r\n\r\n'); await w.drain()
        raw = await asyncio.wait_for(r.read(-1), 10)
    finally:
        w.close()
    head, _, body = raw.partition(b'\r\n\r\n')
    if b'chunked' in head.lower(): body = dechunk(body)
    names = set()
    for m in json.loads(body or b'{}').get('models', []):
        name = str(m.get('name', ''))
        if m.get('remote_host') or m.get('remote_model') or re.search(r'[-:]cloud\b', name): continue
        names.add(name)
        if name.endswith(':latest'): names.add(name[:-7])
    _models.update(at=time.monotonic(), names=names)
    return names


def dechunk(b):
    out, i = bytearray(), 0
    while True:
        j = b.find(b'\r\n', i)
        if j < 0: break
        size = int(b[i:j].split(b';')[0] or b'0', 16)
        if size == 0: break
        out += b[j + 2:j + 2 + size]; i = j + 2 + size + 2
    return bytes(out)


async def ollama(c_reader, c_writer, slots):
    if slots.locked(): c_writer.close(); return
    async with slots:
        try:
            head = await asyncio.wait_for(c_reader.readuntil(b'\r\n\r\n'), FIRST_BYTE)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError, OSError):
            c_writer.close(); return
        try:
            lines = head.decode('latin-1').split('\r\n')
            method, path, version = lines[0].split(' ')
            headers = {}
            for line in lines[1:]:
                if not line: continue
                k, _, v = line.partition(':')
                headers[k.strip().lower()] = v.strip()
        except ValueError:
            refuse(c_writer, '400 Bad Request', 'malformed request'); c_writer.close(); return
        path = path.split('?', 1)[0]
        if (method, path) not in ALLOWED or not version.startswith('HTTP/1.'):
            refuse(c_writer, '403 Forbidden', f'{method} {path[:60]} is not allowed'); c_writer.close(); return
        if 'transfer-encoding' in headers:
            refuse(c_writer, '411 Length Required', 'chunked requests are not accepted'); c_writer.close(); return
        n = int(headers.get('content-length', '0') or 0) if headers.get('content-length', '0').isdigit() else -1
        if n < 0 or n > MAX_BODY or (method == 'POST' and n == 0):
            refuse(c_writer, '413 Payload Too Large', 'body missing or too large'); c_writer.close(); return
        try:
            body = await asyncio.wait_for(c_reader.readexactly(n), 60) if n else b''
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError, OSError):
            c_writer.close(); return
        if method == 'POST':
            try:
                req = json.loads(body)
                model = req.get('model') if isinstance(req, dict) else None
                if not isinstance(model, str): raise ValueError
                names = await installed_models()
            except (ValueError, OSError, asyncio.TimeoutError):
                refuse(c_writer, '400 Bad Request', 'request body or model list unreadable'); c_writer.close(); return
            if model not in names:
                refuse(c_writer, '403 Forbidden', f'model {model[:80]!r} is not installed on the Mac'); c_writer.close(); return
        try:
            u_reader, u_writer = await asyncio.wait_for(asyncio.open_connection(*OLLAMA), 10)
        except (OSError, asyncio.TimeoutError):
            refuse(c_writer, '502 Bad Gateway', 'Ollama on the Mac is not answering'); c_writer.close(); return
        keep = ''.join(f'{k}: {v}\r\n' for k, v in headers.items()
                       if k not in ('connection', 'keep-alive', 'proxy-connection', 'upgrade', 'te', 'content-length'))
        u_writer.write(f'{method} {path} HTTP/1.1\r\n{keep}Content-Length: {n}\r\nConnection: close\r\n\r\n'.encode('latin-1') + body)
        await bridge(c_reader, c_writer, u_reader, u_writer, IDLE['ollama'])


async def main():
    page_slots, ollama_slots = asyncio.Semaphore(SLOTS['page']), asyncio.Semaphore(SLOTS['ollama'])
    servers = [await asyncio.start_server(lambda r, w: page(r, w, page_slots), '0.0.0.0', 8765),
               await asyncio.start_server(lambda r, w: ollama(r, w, ollama_slots), '0.0.0.0', 11434, limit=16384)]
    log(':8765 -> app:8765 (page)'); log(':11434 -> host.docker.internal:11434 (Ollama: tags, chat, embed; installed models only)')
    stop = asyncio.Event()
    for s in (signal.SIGTERM, signal.SIGINT): asyncio.get_running_loop().add_signal_handler(s, stop.set)
    await stop.wait()
    for s in servers: s.close()


if __name__ == '__main__':
    if len(sys.argv) > 1: sys.exit('relay: takes no arguments; its routes are fixed in the code')
    asyncio.run(main())
