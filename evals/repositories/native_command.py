"""Bounded execution shared by native evals and the experimental feedback helper."""
import os
import signal
import subprocess
import threading
import time

MAX_LOG_BYTES = 8 * 1024 * 1024


def command(argv, work, env, logs, name, timeout=300):
    started = time.monotonic()
    path = logs / (name + '.log')
    size, overflow = 0, False
    def stop(proc):
        try:
            if os.name == 'posix':
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=True)
        except (ProcessLookupError, OSError, subprocess.SubprocessError):
            try:
                proc.kill()
            except OSError:
                pass
    with path.open('wb') as output:
        try:
            proc = subprocess.Popen(argv, cwd=work, env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, start_new_session=os.name == 'posix')
        except OSError as error:
            output.write(type(error).__name__.encode())
            return {'exit_code': None, 'timed_out': False, 'duration_seconds': round(time.monotonic()-started, 3),
                    'output_bytes': 0, 'output_within_limit': True}, type(error).__name__
        def drain():
            nonlocal size, overflow
            try:
                while chunk := proc.stdout.read(65536):
                    remaining = max(0, MAX_LOG_BYTES - size)
                    output.write(chunk[:remaining])
                    size += len(chunk)
                    if size > MAX_LOG_BYTES:
                        overflow = True
                        stop(proc)
                        break
            finally:
                proc.stdout.close()
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        timed_out = False
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop(proc)
            proc.wait(timeout=10)
            code = None
        except BaseException:
            # An interrupted caller must not leave its native test process alive.
            stop(proc)
            try:
                proc.wait(timeout=10)
            finally:
                reader.join(timeout=10)
            raise
        reader.join(timeout=5)
        if reader.is_alive():
            stop(proc)
            reader.join(timeout=5)
            code = None
    text = path.read_text(errors='replace')
    return {'exit_code': code, 'timed_out': timed_out, 'duration_seconds': round(time.monotonic()-started, 3),
            'output_bytes': size, 'output_within_limit': not overflow}, text


def command_passed(result):
    return result["exit_code"] == 0 and not result["timed_out"] and result["output_within_limit"]

