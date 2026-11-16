"""Run local tool tests and write clearly labelled machine-readable evidence."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom-code"))
sys.path.insert(0, str(ROOT))


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.cases.append({"id": test.id(), "status": "passed"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.cases.append({"id": test.id(), "status": "failed"})

    def addError(self, test, err):
        super().addError(test, err)
        self.cases.append({"id": test.id(), "status": "error"})

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.cases.append({"id": str(subtest), "status": "failed"})


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    output = ROOT / "results" / "local-tool-tests.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({
        "kind": "local_python_tool_tests", "is_cresta_conversation_export": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tests_run": result.testsRun, "successful": result.wasSuccessful(), "cases": result.cases,
    }, indent=2) + "\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
