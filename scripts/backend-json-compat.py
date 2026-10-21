#!/usr/bin/python3
"""Normalize WeTypeX backend JSON to ASCII escapes; never save input."""
import json
import subprocess
import sys
import threading

backend = subprocess.Popen(
    ['/usr/bin/fcitx5-wetypex-backend'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
)

def forward_responses():
    try:
        for line in backend.stdout:
            response = json.loads(line)
            sys.stdout.buffer.write(
                (json.dumps(response, ensure_ascii=True) + '\n').encode('ascii'))
            sys.stdout.buffer.flush()
    except (BrokenPipeError, ValueError, UnicodeError):
        backend.terminate()

reader = threading.Thread(target=forward_responses, daemon=True)
reader.start()
try:
    for line in sys.stdin.buffer:
        backend.stdin.write(line)
        backend.stdin.flush()
except BrokenPipeError:
    pass
finally:
    backend.stdin.close()
    backend.wait()
    reader.join(timeout=2)
