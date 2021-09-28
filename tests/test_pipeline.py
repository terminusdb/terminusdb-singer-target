import json
import os
import shutil
import subprocess


def test_happy_path(docker_url, tmp_path):
    this_dir = os.path.dirname(os.path.abspath(__file__))
    shutil.copy(this_dir + "/tap_ip.py", tmp_path)
    os.chdir(tmp_path)
    config = {"endpoint": docker_url, "database": "test_singer"}
    with open("config.json", "w") as file:
        json.dump(config, file)
    command = "python tap_ip.py"
    result = subprocess.run(command.split(" "), capture_output=True, check=True)
    command = "target-terminusdb -c config.json"
    result = subprocess.run(
        command.split(" "), capture_output=True, check=True, input=result.stdout
    )
    assert result.stdout == b"Schema inserted\nDocuments inserted\n"
