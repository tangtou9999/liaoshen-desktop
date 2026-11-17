import hashlib
import json
from pathlib import Path
import unittest
class PromptTests(unittest.TestCase):
    def test_original_prompt_bytes(self):
        root=Path(__file__).resolve().parents[1]
        manifest=json.loads((root/'prompt_sha256.json').read_text())
        self.assertEqual(len(manifest),5)
        for name,digest in manifest.items():
            self.assertEqual(hashlib.sha256((root/'liaoshen/assets'/name).read_bytes()).hexdigest(),digest,name)
