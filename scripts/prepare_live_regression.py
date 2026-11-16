"""Prepare supplemental real-API cases with fresh, script-generated email addresses."""
import copy
import re
from pathlib import Path
from uuid import uuid4

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'unsupported-route', 'listed-flight-outside-shortlist',
            'passenger-email-conflict', 'search-outage', 'save-outage', 'booking-timeout'}


def prepare():
    out = ROOT / 'test_cases/live_regression/final'
    out.mkdir(parents=True, exist_ok=True)
    for path in sorted((ROOT / 'test_cases').glob('*.yaml')):
        if path.stem in EXCLUDED:
            continue
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict) or 'testCaseConversation' not in data:
            continue
        data.pop('mockConfig', None)
        data['displayName'] = 'AI Agent 51 | live regression | ' + path.stem
        data['tags'] = ['ai-agent-51', 'live-api', 'supplemental-regression']
        caller = data['testCaseConversation'].get('flowSimulatedConversation')
        if caller:
            caller['promptTemplate'] = re.sub(r'jane\.[a-f0-9]+@example\.com',
                                            'jane.' + uuid4().hex + '@example.com', caller['promptTemplate'])
        (out / path.name).write_text(yaml.safe_dump(data, sort_keys=False))
    data = copy.deepcopy(yaml.safe_load((out / 'happy-path-live.yaml').read_text()))
    data['displayName'] = 'AI Agent 51 | live regression | defer-seat-only'
    data['description'] = 'A seat-only deferral requires clarification, not disconnection.'
    caller = data['testCaseConversation']['flowSimulatedConversation']
    caller['promptTemplate'] = re.sub(r'jane\.[a-f0-9]+@example\.com',
                                    'jane.' + uuid4().hex + '@example.com', caller['promptTemplate'])
    caller['promptTemplate'] += (
        ' Override the usual seat answer: when first asked about seats, say only: '
        'I want to book now but choose my seat later. Do not defer booking. '
        'If the agent explains that the API requires window, aisle, or middle, choose '
        'window and explicitly authorize the booking. Do not insist on an unsupported '
        'no-preference value. After successful booking say you need nothing else.')
    judge = data['testCaseConversation']['momentEvaluators']['evaluators'][0]
    judge['id'] = 'behavior-defer-seat-only'
    rule = judge['momentData']['aiAgentEvaluationMomentData']['conversationEvaluationRule']
    rule['conversationBinaryLlmEvaluator']['promptTemplate'] = (
        'Additionally require that a seat-only deferral is clarified without ending '
        'the call. Fail if the agent says seats can be changed or selected after booking, '
        'guarantees a seat location, or invents any airline seating policy. '
        'The documented booking API requires seat_preference to be window, aisle, '
        'or middle; no no-preference value is accepted. Explaining that one of these '
        'preferences is required to submit this booking is a supported API constraint, '
        'not an invented airline policy or a guaranteed seat assignment. Require '
        'acknowledgment that the caller wants to continue booking now. The caller then '
        'chooses an API-supported seat preference and '
        'explicitly authorizes the booking. No hold is warranted merely for a seat question.\n'
        + rule['conversationBinaryLlmEvaluator']['promptTemplate'])
    (out / 'defer-seat-only.yaml').write_text(yaml.safe_dump(data, sort_keys=False))
    print('Prepared 22 supplemental live cases with fresh synthetic emails.')


if __name__ == '__main__':
    prepare()
