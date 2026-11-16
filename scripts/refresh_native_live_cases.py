"""Refresh only live native-case emails, preserving controlled fixture contracts.

Run before pushing/executing the shared native suite again. Reusing a passenger
email can produce a real API conflict unrelated to the scenario under test.
"""
import json
import re
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def refresh():
    manifest = json.loads((ROOT / 'tests/native-manifest.json').read_text())
    for case in manifest['cases']:
        if case['mode'] != 'live_api':
            continue
        path = ROOT / 'test_cases' / (case['id'] + '.yaml')
        text, count = re.subn(r'jane\.[a-f0-9]+@example\.com',
                             'jane.' + uuid4().hex + '@example.com', path.read_text())
        if count != 1:
            raise ValueError(f'{path.name}: expected one generated synthetic email')
        path.write_text(text)
        print(f'Refreshed {path.name}')


if __name__ == '__main__':
    refresh()
