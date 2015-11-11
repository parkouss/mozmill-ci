#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import sys
import tarfile
import time
import urllib

from subprocess import check_call

import start


DIR_TEST_ENV = "test/venv"
DIR_JENKINS_ENV = "jenkins-env"
VERSION_VIRTUALENV = "12.0.5"

os.environ["JENKINS_HOME"] = "jenkins-master"


def check_patches():
    print "Checking patches"
    check_call(["./test/check_patches.sh"])


class Jenkins(object):
    def __init__(self):
        if self._require_venv_setup():
            print "Running setup"
            check_call(["./setup.sh", DIR_JENKINS_ENV])
        print "Starting Jenkins"
        self.proc = start.start_jenkins()

    def _require_venv_setup(self):
        if os.path.exists(DIR_JENKINS_ENV) and not os.environ.get('CI'):
            print "Jenkins environment already exists!"
            while True:
                user_input = raw_input("Would you like to recreate it? (y/n): ")
                if user_input.lower().startswith("y"):
                    break
                elif user_input.lower().startswith("n"):
                    return False
        return True

    def wait_for_started(self):
        import requests

        max_time = time.time() + 60
        session = requests.Session()

        while time.time() <= max_time:
            try:
                if session.get("http://localhost:8080").status_code == 200:
                    return
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(0.5)
        raise Exception("Jenkins did not start successfully - check the logs.")

    def kill(self):
        # try to kill nicely first
        self.proc.terminate()
        attempt = 0
        while self.proc.poll() is None:
            attempt += 1
            if attempt > 500:
                self.proc.kill()  # hard kill
                break
            time.sleep(0.001)


def virtualenv_create():
    if os.path.exists(DIR_TEST_ENV):
        print "Using virtual environment in ", DIR_TEST_ENV
        return

    tar_fname = 'virtualenv-%s.tar.gz' % VERSION_VIRTUALENV
    print ('Creating a virtual environment (version %s) in %s'
           % (VERSION_VIRTUALENV, DIR_TEST_ENV))
    urllib.urlretrieve(
        'https://pypi.python.org/packages/source/v/virtualenv/%s' % tar_fname,
        tar_fname
    )

    tar = tarfile.open(name=tar_fname)
    tar.extractall(path='.')
    check_call([sys.executable,
                "virtualenv-%s/virtualenv.py" % VERSION_VIRTUALENV,
                DIR_TEST_ENV])


def virtualenv_activate():
    activate_this_file = os.path.join(DIR_TEST_ENV, 'bin', 'activate_this.py')
    execfile(activate_this_file, dict(__file__=activate_this_file))


def run_tests():
    check_patches()
    jenkins = Jenkins()
    try:
        jenkins.wait_for_started()
    except Exception as exc:
        print str(exc)
        jenkins.kill()
        sys.exit(1)
    try:
        virtualenv_create()
        virtualenv_activate()
        check_call(['pip', 'install', 'selenium'])
        check_call(['python', "test/configuration/save_config.py"])
    finally:
        print "Killing Jenkins"
        jenkins.kill()
    check_call(["git", "--no-pager", "diff", "--exit-code"])


if __name__ == '__main__':
    this_dir = os.path.dirname(os.path.realpath(__file__))
    os.chdir(this_dir)
    run_tests()
