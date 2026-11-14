#!/usr/bin/env python3
"""Prepare an exact wheelhouse cache and install without an index on cache hits."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request


def prepare(env=os.environ, today=None, latest=None):
    version = env.get('VERSION', '').strip()
    pin = env.get('VERSION_FILE', '')
    if not version and pin and Path(pin).is_file():
        lines = Path(pin).read_text().splitlines()
        version = lines[0].strip() if lines else ''
        if not version:
            raise ValueError('docassert version file is empty')
    if not version:
        if latest is None:
            with urllib.request.urlopen('https://pypi.org/pypi/docassert/json', timeout=30) as response:
                latest = json.load(response)['info']['version']
        version = latest
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('docassert version must be an exact X.Y.Z release')
    extras = env.get('EXTRAS', '').strip()
    if extras and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*(,[A-Za-z0-9][A-Za-z0-9._-]*)*', extras):
        raise ValueError('extras must be comma-separated pip extra names')
    extras = ','.join(sorted(set(extras.lower().split(',')))) if extras else ''
    spec = 'docassert' + (f'[{extras}]' if extras else '') + f'=={version}'
    # Refresh dependency resolution weekly even when docassert stays pinned.
    week = (today or datetime.date.today()).strftime('%G-W%V')
    identity = '|'.join((spec, platform.system(), platform.machine(),
                         platform.python_implementation(), platform.python_version(), week))
    key = 'docassert-wheels-v1-' + hashlib.sha256(identity.encode()).hexdigest()
    directory = str(Path(env['RUNNER_TEMP']) / key)
    return {'spec': spec, 'key': key, 'directory': directory}


def install(spec, directory, run=subprocess.run, sleep=time.sleep):
    wheelhouse = Path(directory)
    marker = wheelhouse / '.complete'
    pip = [sys.executable, '-m', 'pip']
    if not marker.is_file() or marker.read_text() != spec:
        for attempt in range(4):
            shutil.rmtree(wheelhouse, ignore_errors=True)
            wheelhouse.mkdir(parents=True)
            result = run(pip + ['wheel', '--quiet', '--wheel-dir', str(wheelhouse), spec], check=False)
            if result.returncode == 0:
                marker.write_text(spec)
                break
            if attempt == 3:
                raise RuntimeError('could not prepare docassert wheels after 4 attempts')
            print('wheel preparation failed; retrying in 75s', flush=True)
            sleep(75)
    # An exact wheelhouse contains docassert AND its resolved dependencies.
    # No network fallback: a broken cache must fail visibly, not inflate downloads.
    run(pip + ['install', '--quiet', '--no-index', '--find-links', str(wheelhouse), spec], check=True)
    run(['docassert', '--version'], check=True)


def main():
    if sys.argv[1] == 'prepare':
        values = prepare()
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            for key, value in values.items():
                output.write(f'{key}={value}\n')
    elif sys.argv[1] == 'install':
        install(os.environ['DOCASSERT_SPEC'], os.environ['DOCASSERT_WHEELHOUSE'])
    else:
        raise ValueError('unknown installer phase')


if __name__ == '__main__':
    main()
