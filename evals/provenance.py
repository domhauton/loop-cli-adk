"""Content fingerprints for SDK checkouts, including uncommitted source changes."""
import hashlib
import os
from pathlib import Path
import subprocess

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_SOURCE_BYTES = 128 * 1024 * 1024


def snapshot(root):
    root = Path(root).resolve()
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root)
    revision = git('rev-parse', 'HEAD').decode().strip()
    names = set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')) - {b''}
    digest, size = hashlib.sha256(), 0
    for name in sorted(names):
        path = root / os.fsdecode(name)
        if path.is_symlink():
            content = b'link\0' + os.fsencode(os.readlink(path))
        elif not path.exists():
            content = b'deleted\0'
        else:
            with path.open('rb') as stream:
                content = b'file\0' + stream.read(MAX_FILE_BYTES + 1)
            if len(content) > MAX_FILE_BYTES + 5:
                raise ValueError('source file exceeds fingerprint size limit')
        size += len(content)
        if size > MAX_SOURCE_BYTES:
            raise ValueError('source tree exceeds fingerprint size limit')
        digest.update(len(name).to_bytes(8, 'big') + name)
        digest.update(hashlib.sha256(content).digest())
    return {'revision': revision, 'sha256': digest.hexdigest()}
