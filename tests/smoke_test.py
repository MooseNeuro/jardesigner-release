"""End-to-end smoke test for an installed jardesigner package.

Starts the installed `jardesigner` command on a non-default port, then
exercises it the way the browser does: static UI, tutorial list, staging of
every file the proto registries point at, and two simulations driven over
Socket.IO (Hodgkin-Huxley spiking, and a chemical oscillator whose reaction
graph must be laid out by Graphviz).

Usage:
    pip install jardesigner "python-socketio[client]" websocket-client
    python tests/smoke_test.py

Exits non-zero on the first failure. Runs unchanged on Linux, macOS and
Windows.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from importlib import resources

import requests
import socketio

PORT = int(os.environ.get('JARDESIGNER_SMOKE_PORT', '5077'))
BASE = f'http://127.0.0.1:{PORT}'

HH_MODEL = {
    'filetype': 'jardesigner', 'version': '1.0', 'runtime': 0.1,
    'cellProto': {'type': 'soma', 'somaDia': 5e-4, 'somaLen': 5e-4},
    'chanProto': [
        {'type': 'builtin', 'source': 'make_Na()', 'name': 'Na'},
        {'type': 'builtin', 'source': 'make_K_DR()', 'name': 'KDR'},
    ],
    'chanDistrib': [
        {'proto': 'Na', 'path': 'soma', 'Gbar': 1200},
        {'proto': 'KDR', 'path': 'soma', 'Gbar': 360},
    ],
    'stims': [{'type': 'field', 'path': 'soma', 'field': 'inject',
               'expr': '(t>0.02 && t<0.08)*1e-7'}],
    'plots': [{'path': 'soma', 'field': 'Vm', 'title': 'Soma Vm'}],
}

CHEM_MODEL = {
    'filetype': 'jardesigner', 'version': '1.0', 'runtime': 5,
    'cellProto': {'type': 'ballAndStick'},
    'chemProto': [{'type': 'builtin', 'source': 'makeChemOscillator()',
                   'name': 'Oscillator'}],
    'chemDistrib': [{'proto': 'Oscillator', 'path': 'dend#', 'type': 'dend',
                     'diffusionLength': 2e-6}],
    'plots': [{'path': 'dend#', 'field': 'conc', 'relpath': 'Oscillator/a[]',
               'title': 'Oscillator a'}],
}


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f'  ok  {msg}')


def wait_for_server(proc, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f'server exited early with code {proc.returncode}')
        try:
            if requests.get(BASE + '/', timeout=2).status_code == 200:
                return
        except requests.ConnectionError:
            pass
        time.sleep(1)
    raise AssertionError(f'server did not answer on {BASE} within {timeout}s')


def run_simulation(model, timeout=180):
    """Drive one simulation like the frontend does; return (plot, events)."""
    client_id = 'smoke-' + uuid.uuid4().hex[:12]
    channel = str(uuid.uuid4())
    events = []
    sio = socketio.Client()

    @sio.on('*')
    def _any(event, data=None):
        events.append((event, data if isinstance(data, dict) else {}))

    sio.connect(BASE, transports=['websocket'])
    try:
        sio.emit('register_client', {'clientId': client_id})
        sio.emit('join_sim_channel', {'data_channel_id': channel})
        time.sleep(0.5)

        r = requests.post(BASE + '/launch_simulation', timeout=30, json={
            'config_data': model, 'client_id': client_id,
            'data_channel_id': channel})
        body = r.json()
        check(r.status_code == 200 and body.get('status') == 'success',
              f'launch_simulation accepted ({body.get("message", "")})')

        def types():
            return [d.get('type') for e, d in events if e == 'simulation_data']

        def errors():
            return [d for e, d in events if e == 'simulation_error']

        deadline = time.time() + timeout
        while 'scene_init' not in types():
            if errors() or time.time() > deadline:
                raise AssertionError(f'model build failed: {errors() or "timeout"}')
            time.sleep(0.5)
        sio.emit('sim_command', {'pid': body['pid'], 'command': 'start', 'params': {}})
        while 'sim_end' not in types():
            if errors() or time.time() > deadline:
                raise AssertionError(f'simulation failed: {errors() or "timeout"}')
            time.sleep(0.5)
        check(not errors(), 'no simulation_error events')

        r = requests.get(f'{BASE}/session_file/{client_id}/plot.json', timeout=30)
        check(r.status_code == 200, 'plot.json served')
        return r.json(), events
    finally:
        sio.disconnect()


def main():
    exe = shutil.which('jardesigner')
    check(exe is not None, f'jardesigner command on PATH ({exe})')

    proc = subprocess.Popen([exe, '--no-browser', '--port', str(PORT)])
    try:
        wait_for_server(proc)
        print(f'server up on {BASE}')

        r = requests.get(BASE + '/', timeout=10)
        check('<div id="root">' in r.text or 'id="root"' in r.text, 'UI index.html served')
        check(':5000' not in r.text, 'index.html has no hardcoded port 5000')

        examples = requests.get(BASE + '/examples', timeout=10).json()
        check(len(examples) > 0, f'{len(examples)} tutorials listed')

        registry = resources.files('jardesigner').joinpath('proto_registry')
        staged = 0
        for kind in ('chem', 'chan', 'morpho'):
            data = json.loads(registry.joinpath(f'{kind}_protos.json').read_text(encoding='utf-8'))
            items = data if isinstance(data, list) else next(
                v for v in data.values() if isinstance(v, list))
            for item in items:
                if not item.get('server_file'):
                    continue
                r = requests.post(f'{BASE}/proto_stage/{item["id"]}/smoke-staging', timeout=30)
                check(r.status_code == 200, f'stage {kind} proto {item["id"]}')
                staged += 1
        check(staged > 0, f'{staged} registry files staged')

        print('HH spiking model:')
        plot, _ = run_simulation(HH_MODEL)
        vm = plot['plots'][0]['val'][0]
        check(len(vm) > 100, f'{len(vm)} Vm samples')
        check(max(vm) > 0, f'action potential fired (peak {max(vm):.1f} mV)')

        print('Chemical oscillator model:')
        plot, events = run_simulation(CHEM_MODEL)
        conc = plot['plots'][0]['val'][0]
        # Chem plots default to a 1 s sample interval: 5 s run -> 6 samples.
        check(len(conc) >= 5 and max(conc) > min(conc),
              f'concentration trace recorded ({len(conc)} samples, '
              f'{min(conc):.1f}-{max(conc):.1f} uM)')
        graphs = [d.get('reactionGraph') for e, d in events
                  if e == 'simulation_data' and d.get('type') == 'scene_init']
        check(any(g and g.get('objects') for g in graphs), 'reaction graph laid out')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()

    print('\nAll smoke tests passed.')


if __name__ == '__main__':
    try:
        main()
    except AssertionError as e:
        print(f'\nFAILED: {e}')
        sys.exit(1)
