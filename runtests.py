#!/usr/bin/env python

import os
import sys

import django
from django.conf import settings
from django.test.utils import get_runner


def run_tests():
    test_project_dir = os.path.join(os.path.dirname(__file__), 'test_project')
    sys.path.insert(0, test_project_dir)

    os.environ['DJANGO_SETTINGS_MODULE'] = 'test_project.settings'
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["tests"])
    sys.exit(bool(failures))

if __name__ == "__main__":
    run_tests()
