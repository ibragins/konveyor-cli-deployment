import logging
import os
import random
import re
import shutil
import string
import json
import sys
import paramiko
import requests
import platform

import config
from utils.const import zip_urls

# from utils.const import zip_urls

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers = [
        logging.StreamHandler(sys.stdout)  # Redirecting to stdout
    ]
)


import subprocess
import logging

def run_command(command, fail_on_failure=True, client=None):
    logging.info(f"Executing command: {command}")
    try:
        if client:
            _stdin, stdout, _stderr = client.exec_command(command)

            out = stdout.read().decode()
            err = _stderr.read().decode()
            exit_status = stdout.channel.recv_exit_status()

            # logging.info(f"[REMOTE] exit_code={exit_status}")
            if exit_status != 0 and fail_on_failure:
                raise SystemExit(
                    f"Remote command failed with exit code {exit_status}\nSTDOUT:\n{out}\nSTDERR:\n{err}"
                )

            return out, err
        else:
            result = subprocess.run(
                command,
                shell=True,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
            )
            if result.returncode != 0 and fail_on_failure:
                raise SystemExit(
                    f"Local command failed with exit code {result.returncode}\n"
                    f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                )
            return result.stdout, result.stderr
    except Exception as err:
        raise SystemExit(f"There was an issue running a command: {err}")



def read_file(output_file):
    """
    Opens a file for reading
    :param output_file:
    :return: opened file's content
    """
    try:
        with open(output_file, 'r') as file:
            logging.info(f"File opened successfully: {output_file}")
            return file.read()
    except Exception as err:
        raise SystemExit(f"There was an error opening file: {err}")

def convert_to_json(file):
    """
    Converts incoming string to JSON format
    :param file: String to be converted
    :return: JSON
    """
    # print(f"Json got: {file}")
    try:
        match = re.search(r'\{.*\}', file, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in input.")

        json_str = match.group(0)
        parsed = json.loads(json_str)
        logging.info("String was converted to JSON successfully!")
        return parsed

    except Exception as err:
        raise SystemExit(f"There was an error converting string to JSON format: {err}")


def connect_ssh(ip_address):
    SSH_HOST = ip_address
    SSH_USER = config.SSH_USER
    SSH_KEY = config.SSH_KEY
    client = paramiko.SSHClient()
    try:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(SSH_HOST, username=SSH_USER, key_filename=SSH_KEY)
        logging.info(f"Connected to host {ip_address}")
        return client
    except Exception as err:
        client.close()
        raise SystemExit("There was an issue connecting to host by ssh: {}".format(err))


def get_target_dependency_path(client=None):
    """
    Gets home folder path of the user script is running from
    :param: client: SSH client for getting home dir from remote host
    :return: String contains folder name
    """
    if client:
        try:
            stdin, stdout, stderr = client.exec_command('echo $HOME')
            home_dir = stdout.read().decode().strip()
            if not home_dir:
                # В качестве запасного варианта используем 'pwd'
                stdin, stdout, stderr = client.exec_command('pwd')
                home_dir = stdout.read().decode().strip()
        except Exception as err:
            raise SystemExit("There was an issue getting home dir of remote host: {}".format(err))
    else:
        home_dir = os.path.expanduser("~")

    return os.path.join(home_dir, ".kantra")


def clear_folder (path):
    """
    Clears folder by removing it with all content and creating it again
    :param path: Path of the folder to be cleared
    """
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
            logging.info(f"Folder was removed successfully: {path}")
        except Exception as err:
            logging.error(f"Error {err} when trying to delete folder: {path}")

    try:
        os.makedirs(path, exist_ok=True)
        logging.info(f"Folder was created successfully: {path}")
    except Exception as err:
        logging.error(f"Couldn't create a folder: {path}")
        raise SystemExit ("There was an issue creating a folder: {}".format(err))


def create_random_folder(base_path):
    """
    Creates a random folder with a name of 8 characters inside the specified path.

    :param base_path: Path where the folder will be created
    :return: Full path to the created folder
    """
    # Ensure the base path exists
    os.makedirs(base_path, exist_ok=True)

    # Generate a random folder name with 8 characters
    folder_name = ''.join(random.choices(string.ascii_letters, k=8))
    full_path = os.path.join(base_path, folder_name)

    # Create the folder
    os.makedirs(full_path)

    return full_path


def get_latest_upstream_dependency(user, repo, asset_name):
    """
    Downloads latest U/S dependency file from github
    :param user: Owner's use
    :param repo: Repo where file is located
    :param asset_name:
    :return:
    """
    url = f'https://api.github.com/repos/{user}/{repo}/releases'
    response = requests.get(url)

    if response.status_code == 200:
        releases = response.json()
        for release in releases:
            # Check if the release is a pre-release (beta/alpha)
            if release['prerelease']:
                for asset in release['assets']:
                    if asset['name'] == asset_name:
                        return asset['browser_download_url']
    else:
        logging.error(f"Error fetching releases: {response.status_code}")
        return None


def pull_stage_ga_dependency_file(mta_version, repo):
    os_name, machine = get_os_platform()
    dependency_file_name = f'mta-{mta_version}-cli-{os_name}-{machine}.zip'
    dependency_file_url=zip_urls.get(repo).format(ver=mta_version) + dependency_file_name
    download_file(dependency_file_url, dependency_file_name)
    return dependency_file_name


def download_file(url, local_filename):
    response = requests.get(url, stream=True,verify=False)
    if response.status_code == 200:
        with open(local_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(f"File saved as {local_filename}")
    else:
        logging.error(f"Error downloading file: {response.status_code}")


def get_os_platform ():
    os_name = platform.system().lower()
    machine = platform.machine().lower()

    if "aarch64" in machine or "arm64" in machine:
        machine = "arm64"
    elif "x86_64" in machine or "amd64" in machine:
        machine = "amd64"
    else:
        machine = "unknown"
    return os_name, machine


def send_file_by_ssh(client):
    pass