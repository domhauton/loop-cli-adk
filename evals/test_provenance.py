from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from provenance import snapshot


class ProvenanceTests(unittest.TestCase):
    def test_same_head_cannot_hide_source_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def git(*args):
                subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)
            git('init', '-q')
            (root / 'source.txt').write_text('original')
            (root / '.gitignore').write_text('cache/\n')
            git('add', '.')
            git('-c', 'user.name=Eval', '-c', 'user.email=eval@example.invalid', 'commit', '-qm', 'fixture')
            original = snapshot(root)
            (root / 'cache').mkdir()
            (root / 'cache/output').write_text('ignored')
            self.assertEqual(snapshot(root), original)
            (root / 'source.txt').write_text('edited')
            modified = snapshot(root)
            self.assertEqual(modified['revision'], original['revision'])
            self.assertNotEqual(modified['sha256'], original['sha256'])
            (root / 'source.txt').write_text('original')
            (root / 'new.py').write_text('untracked source')
            self.assertNotEqual(snapshot(root), original)
            (root / 'new.py').unlink()
            (root / 'source.txt').unlink()
            self.assertNotEqual(snapshot(root), original)
