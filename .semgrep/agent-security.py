import json
import os
import subprocess


def process(command):
    # ruleid: agent-no-shell-interpolation
    subprocess.run(command, shell=True)
    # ruleid: agent-no-shell-interpolation
    os.system(command)
    # ok: agent-no-shell-interpolation
    subprocess.run(["echo", command], shell=False)


def deserialize(content):
    # ruleid: agent-no-dynamic-python
    eval(content)
    # ruleid: agent-no-dynamic-python
    exec(content)
    # ok: agent-no-dynamic-python
    return json.loads(content)


def remote(session, url):
    import requests

    # ruleid: agent-verify-tls
    requests.get(url, verify=False)
    # ok: agent-verify-tls
    return session.get(url, verify=True)
