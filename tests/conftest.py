import os
import subprocess
import time

import pytest
import requests

MAX_CONTAINER_STARTUP_TIME = 30


def pytest_addoption(parser):
    parser.addoption("--docker-compose", action="store", default=None)


def is_docker_installed():
    try:
        output = subprocess.run(["docker", "--version"], stderr=subprocess.PIPE)
    except FileNotFoundError:
        return False
    return output.returncode == 0


pytestmark = pytest.mark.skipif(
    not is_docker_installed(), reason="docker not installed"
)


@pytest.fixture(scope="module")
def docker_url(pytestconfig):
    # we are using subprocess in case we need to access some of the outputs
    # most likely
    pytestconfig.getoption("docker_compose")
    output = subprocess.run(
        [
            "docker-compose",
            "--file",
            os.path.dirname(os.path.realpath(__file__)) + "/test-docker-compose.yml",
            "up",
            "-d",
        ],
        stderr=subprocess.PIPE,
    )
    if output.returncode != 0:
        raise RuntimeError(output.stderr)

    test_url = "http://127.0.0.1:6366"
    is_server_started = False

    seconds_waited = 0
    while not is_server_started:
        service = subprocess.run(
            [
                "docker-compose",
                "--file",
                os.path.dirname(os.path.realpath(__file__))
                + "/test-docker-compose.yml",
                "ps",
                "--services",
                "--filter",
                "status=running",
            ],
            stdout=subprocess.PIPE,
            check=True,
        )

        if service.stdout == b"terminusdb-server\n":
            try:
                response = requests.get(test_url)
                assert response.status_code == 200
                break
            except (requests.exceptions.ConnectionError, AssertionError):
                pass

        seconds_waited += 1
        time.sleep(1)

        if seconds_waited > MAX_CONTAINER_STARTUP_TIME:
            clean_up_container()
            raise RuntimeError("Container was to slow to startup")

    yield test_url
    clean_up_container()


def clean_up_container():
    subprocess.run(
        [
            "docker-compose",
            "--file",
            os.path.dirname(os.path.realpath(__file__)) + "/test-docker-compose.yml",
            "down",
        ],
        check=True,
    )
    subprocess.run(
        [
            "docker-compose",
            "--file",
            os.path.dirname(os.path.realpath(__file__)) + "/test-docker-compose.yml",
            "rm",
            "--force",
            "--stop",
            "-v",
        ],
        check=True,
    )
    subprocess.run(["docker-compose", "down"])
    subprocess.run(["docker-compose", "rm", "--force", "--stop", "-v"])
