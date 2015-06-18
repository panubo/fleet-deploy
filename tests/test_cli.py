from subprocess import call
import os

BIN = os.path.abspath(os.path.join(os.path.split(__file__)[0], '..', 'deploy.py'))


def test_no_args():
    exit_code = call([BIN])
    assert exit_code == 2


def test_help():
    exit_code = call([BIN, '--help'])
    assert exit_code == 0