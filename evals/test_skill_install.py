import json
from pathlib import Path
import sys
import tempfile
import unittest
from repositories.install import SKILL, verify_install


class SkillInstallationTests(unittest.TestCase):
    def test_preservation_grader_rejects_an_installer_that_modifies_host(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                work = root / 'project'
                work.mkdir()
                (work / 'README.md').write_text('host-owned')
                installer = root / 'installer.py'
                installer.write_text('from pathlib import Path\nimport json,sys\n'
                    + f'p=Path({SKILL!r})\n'
                    + 'if p.exists(): sys.exit(2)\n'
                    + 'p.parent.mkdir(parents=True,exist_ok=True)\np.write_text("skill")\n'
                    + ('Path("README.md").write_text("changed")\n' if corrupt else '')
                    + 'print(json.dumps({"mode":"testing","files":[' + repr(SKILL) + ']}))\n')
                result = verify_install([sys.executable, str(installer)], work, root)
                self.assertEqual(result['passed'], not corrupt, result)
                self.assertEqual(result['checks']['host_unchanged'], not corrupt)
