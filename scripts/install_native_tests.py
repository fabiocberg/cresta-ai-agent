"""Install only this exercise's native cases/mocks after explicit owner approval.

Without --apply this prints the plan and performs no platform writes.
--apply does NOT deploy the agent or execute conversations.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.private/platform-test-setup.json'
BASE = 'https://fde-interview-flight-booking.voice-staging.cresta.ai'


def records(value):
    if isinstance(value, dict):
        if 'displayName' in value:
            yield value
        for item in value.values():
            yield from records(item)
    elif isinstance(value, list):
        for item in value:
            yield from records(item)


def resource_id(value):
    if isinstance(value, dict):
        for field in ('id', 'name'):
            if isinstance(value.get(field), str) and value[field]:
                return value[field].rsplit('/', 1)[-1]
        for item in value.values():
            try:
                return resource_id(item)
            except ValueError:
                pass
    raise ValueError('CLI response has no resource ID; inspect response before continuing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Perform platform writes; requires prior owner confirmation')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'tests/native-manifest.json').read_text())
    print(f"Plan: {manifest['test_set']}, {len(manifest['cases'])} cases, 3 endpoints, 10 mock rules.")
    if not args.apply:
        print('Preview only. Agent publication, conversation execution and submission are separate steps.')
        return
    cli = shutil.which('cresta') or str(Path.home() / '.local/bin/cresta')
    state = json.loads(STATE.read_text()) if STATE.exists() else {'endpoints': {}, 'rules': {}, 'cases': {}}

    def save():
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text(json.dumps(state, indent=2) + '\n')

    def call(*cmd, structured=True):
        result = subprocess.run([cli, *cmd, *(['--output', 'json'] if structured else [])],
                                cwd=ROOT, check=True, capture_output=True, text=True)
        return json.loads(result.stdout) if structured else result.stdout

    state['ready'] = False
    save()
    for key, path in manifest['endpoints'].items():
        if key in state['endpoints']:
            continue
        display = f'AI Agent 51 | {key} API'
        existing = call('agent', 'api', 'endpoints', 'list', '--name', display)
        if any(item['displayName'] == display for item in records(existing)):
            raise RuntimeError(f'{display} exists without a locally recorded ID; inspect before adopting it')
        created = call('agent', 'api', 'endpoints', 'create', '--display-name', display,
                       '--method', 'POST', '--production-uri', BASE + path,
                       '--request-logging-mode', 'do-not-log', '--response-logging-mode', 'do-not-log')
        state['endpoints'][key] = resource_id(created)
        save()

    for rule in manifest['rules']:
        key = rule['id']
        if key in state['rules']:
            continue
        endpoint = state['endpoints'][rule['endpoint']]
        display = f'AI Agent 51 | {key}'
        existing = call('agent', 'api', 'mock-rules', 'list', '--endpoint', endpoint, '--limit', '100')
        if any(item['displayName'] == display for item in records(existing)):
            raise RuntimeError(f'{display} exists without a locally recorded ID; inspect before adopting it')
        created = call('agent', 'api', 'mock-rules', 'create', '--display-name', display,
                      '--endpoint', endpoint, '--body-match', json.dumps(rule['body_match']),
                      '--status-code', str(rule['status']), '--body', (ROOT / rule['body_file']).read_text(),
                      '--content-type', 'application/json')
        state['rules'][key] = resource_id(created)
        save()

    # Native YAML already requires strict mode for every controlled case.
    call('agent', 'test', 'push', '--test-local', 'test_cases/*.yaml',
         '--test-set', manifest['test_set'], '--yes', structured=False)
    cases = list(records(call('agent', 'test', 'cases', 'list', '--test-set', manifest['test_set'], '--all')))
    for case in manifest['cases']:
        matches = [item for item in cases if item['displayName'] == case['display_name']]
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one platform case: {case['display_name']}")
        case_id = resource_id(matches[0])
        state['cases'][case['id']] = case_id
        save()
        if case['mode'] == 'strict_mock':
            mock_args = [arg for rule in case['rules'] for arg in ('--mock-rule', state['rules'][rule])]
            call('agent', 'test', 'cases', 'attach-mock-rule', case_id, *mock_args)
            call('agent', 'test', 'cases', 'enable-strict-mode', case_id)
    state['ready'] = True
    save()
    print('Installed cases and attached controlled responses. No conversations executed.')


if __name__ == '__main__':
    main()
