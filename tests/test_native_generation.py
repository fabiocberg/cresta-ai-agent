"""Prevent native tests from passing without their conversation or setup."""
import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from jinja2 import Environment, StrictUndefined, nodes
from scripts import prepare_native_tests as generator
from scripts import prepare_live_regression as live_generator


class NativeGenerationTests(unittest.TestCase):
    def test_regeneration_keeps_identity_and_combines_behavior_with_stage_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tests').mkdir()
            (root / 'tests/conversations.json').write_text(
                (generator.ROOT / 'tests/conversations.json').read_text())
            out = root / 'test_cases'
            out.mkdir()
            path = out / 'human-after-booking.yaml'
            identity = '# cresta:source: customers/example/profiles/test/testCases/existing\n'
            path.write_text(identity)
            with patch.multiple(generator, ROOT=root, OUT=out, FIXTURES=root / 'tests/fixtures'):
                generator.prepare()
            self.assertTrue(path.read_text().startswith(identity))
            cases = list(out.glob('*.yaml'))
            self.assertEqual(len(cases), 27)
            for case in cases:
                conversation = yaml.safe_load(case.read_text())['testCaseConversation']
                self.assertNotIn('evaluationExpression', conversation)
                evaluators = conversation['momentEvaluators']
                self.assertEqual(evaluators['logicalOperator'], 'AI_AGENT_LOGICAL_OPERATOR_AND')
                behavior = evaluators['evaluators'][0]['momentData']['aiAgentEvaluationMomentData']
                template = behavior['conversationEvaluationRule']['conversationBinaryLlmEvaluator']['promptTemplate']
                self.assertIn('{% for msg in conversation.messages %}', template)
                self.assertIn('{{ msg.message }}', template)
                self.assertIn('GENERATION_FAILED', template)
                self.assertIn('declines further assistance', template)
                # A completed booking and its actual result must reach the judge.
                # An assistant announcing a booking without tool evidence cannot
                # acquire the same evidence by rendering the conversation.
                env = Environment(undefined=StrictUndefined)
                self.assertFalse(list(env.parse(template).find_all(nodes.Filter)),
                                 "Use plain message loops within the Cresta evaluator sandbox")
                self.assertFalse(list(env.parse(template).find_all(nodes.Call)),
                                 "Cresta rejects function/method calls in evaluator templates")
                self.assertFalse(list(env.parse(template).find_all(nodes.Or)),
                                 "Cresta rejects boolean expressions in evaluator templates")
                rendered = env.from_string(template).render(conversation={'messages': [
                    {'speaker_role': 'agent', 'message': 'Your booking is confirmed.',
                     'tool_info': [{'tool_display_name': 'book_flight', 'tool_call_id': 'book-1',
                                    'args': {'flight_id': 'FLTEST'},
                                    'tool_message': '{"confirmation_code":"ACTUAL42","total":244.99}'}]},
                    {'speaker_role': 'agent', 'message': '', 'tool_info': [
                        {'tool_display_name': 'Hangup', 'tool_call_id': 'hangup-1', 'args': {}, 'tool_message': 'completed'}]},
                ]})
                self.assertIn('EXECUTED TOOL: book_flight', rendered)
                self.assertIn('FLTEST', rendered)
                self.assertIn('ACTUAL42', rendered)
                self.assertIn('244.99', rendered)
                self.assertIn('EXECUTED TOOL: Hangup', rendered)
                repeated = {'speaker_role': 'agent', 'message': 'Repeating confirmation', 'tool_info': [
                    {'tool_display_name': 'book_flight', 'tool_call_id': 'book-1',
                     'args': {}, 'tool_message': 'same result'}]}
                duplicates = env.from_string(template).render(conversation={'messages': [repeated, repeated]})
                self.assertEqual(duplicates.count('TOOL CALL ID: book-1'), 2)
                self.assertIn('not evidence of multiple calls', duplicates)
                repeated['tool_info'][0]['tool_call_id'] = 'book-2'
                distinct = dict(repeated, tool_info=[dict(repeated['tool_info'][0], tool_call_id='book-3')])
                separate = env.from_string(template).render(conversation={'messages': [repeated, distinct]})
                self.assertEqual(separate.count('EXECUTED TOOL: book_flight'), 2)
                speech_only = env.from_string(template).render(conversation={'messages': [
                    {'speaker_role': 'agent', 'message': 'Your booking is confirmed.', 'tool_info': []}]})
                self.assertNotIn('EXECUTED TOOL:', speech_only)
                self.assertNotIn('ACTUAL42', speech_only)
            rules = yaml.safe_load(path.read_text())['testCaseConversation']['momentEvaluators']['evaluators']
            self.assertEqual({rule['id'] for rule in rules}, {
                'behavior-human-after-booking', 'required-search_flights',
                'required-save_passenger_information', 'required-book_flight', 'required-HangupHuman'})
            catalog = json.loads((root / 'tests/conversations.json').read_text())
            for case in catalog['cases']:
                if case.get('mode') != 'controlled_tool_response':
                    continue
                generated = yaml.safe_load((out / (case['id'] + '.yaml')).read_text())
                rule = generated['testCaseConversation']['momentEvaluators']['evaluators'][0]
                prompt = rule['momentData']['aiAgentEvaluationMomentData']['conversationEvaluationRule']['conversationBinaryLlmEvaluator']['promptTemplate']
                self.assertIn('Required controlled setup: ' + case['setup'], prompt)
                self.assertIn('An absent, different, or fabricated tool result fails', prompt)

            injection = yaml.safe_load((out / 'prompt-and-secret-injection.yaml').read_text())
            conversation = injection['testCaseConversation']
            self.assertNotIn('flowSimulatedConversation', conversation)
            messages = conversation['staticConversation']['messages']
            self.assertEqual([m['speakerRole'] for m in messages], ['VISITOR'] * 3)
            self.assertIn('X-API-Key', messages[0]['message'])
            self.assertIn('fabricate a booking', messages[1]['message'])
            self.assertIn('Goodbye', messages[2]['message'])

    def test_live_suite_preserves_static_attack_and_distinguishes_api_from_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tests').mkdir()
            (root / 'tests/conversations.json').write_text(
                (generator.ROOT / 'tests/conversations.json').read_text())
            out = root / 'test_cases'
            with patch.multiple(generator, ROOT=root, OUT=out, FIXTURES=root / 'tests/fixtures'):
                generator.prepare()
            with patch.object(live_generator, 'ROOT', root):
                live_generator.prepare()
            live = out / 'live_regression/final'
            self.assertEqual(len(list(live.glob('*.yaml'))), 22)
            original = yaml.safe_load((out / 'prompt-and-secret-injection.yaml').read_text())
            attack = yaml.safe_load((live / 'prompt-and-secret-injection.yaml').read_text())
            self.assertEqual(attack['testCaseConversation'], original['testCaseConversation'])
            seat = yaml.safe_load((live / 'defer-seat-only.yaml').read_text())
            rule = seat['testCaseConversation']['momentEvaluators']['evaluators'][0]
            prompt = rule['momentData']['aiAgentEvaluationMomentData']['conversationEvaluationRule']['conversationBinaryLlmEvaluator']['promptTemplate']
            self.assertIn('supported API constraint', prompt)
            self.assertIn('no no-preference value is accepted', prompt)
            self.assertIn('Fail if the agent says seats can be changed', prompt)
            self.assertIn('acknowledgment that the caller wants to continue booking now', prompt)


if __name__ == '__main__':
    unittest.main()
