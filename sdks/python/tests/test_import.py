import json
import subprocess
import sys

import multimcp


def test_version_matches_distribution():
    assert multimcp.__version__ == "0.1.0"


def test_import_does_not_load_provider_sdks():
    probe = (
        "import json, sys, multimcp; "
        "names = ('openai', 'anthropic', 'google.genai'); "
        "print(json.dumps([m for m in names if m in sys.modules]))"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], check=True, capture_output=True, text=True
    ).stdout
    assert json.loads(out) == []
