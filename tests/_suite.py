import contextlib
import functools
import io
import logging
import os
import tempfile
import unittest
from unittest import mock


@contextlib.contextmanager
def offline():
    def blocked(*args, **kwargs):
        raise AssertionError("test tried to use the network")
    keys = {"GEMINI_API_KEY": "", "GROQ_API_KEY": "", "GOOGLE_API_KEY": ""}
    with mock.patch.dict(os.environ, keys), \
            mock.patch("requests.get", blocked), mock.patch("requests.post", blocked):
        yield


def _offline(test):
    @functools.wraps(test)
    def run():
        with offline():
            test()
    return run


def suite_from(namespace):
    suite = unittest.TestSuite()
    for name in sorted(namespace):
        if name.startswith("test_") and callable(namespace[name]):
            suite.addTest(unittest.FunctionTestCase(_offline(namespace[name]), description=name))
    return suite


@contextlib.contextmanager
def temp_data_dir():
    with tempfile.TemporaryDirectory() as folder, \
            mock.patch.dict(os.environ, {"INCIDENT_DATA_DIR": folder}):
        yield folder


@contextlib.contextmanager
def typed(lines):
    feed = iter(lines)

    def fake_input(prompt=""):
        print(prompt, end="")
        try:
            return next(feed)
        except StopIteration:
            raise EOFError

    buffer = io.StringIO()
    with mock.patch("builtins.input", fake_input), contextlib.redirect_stdout(buffer):
        yield buffer


@contextlib.contextmanager
def captured_logs(name):
    messages = []
    handler = logging.Handler()
    handler.emit = lambda record: messages.append(record.getMessage())
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    try:
        yield messages
    finally:
        logger.removeHandler(handler)