import logging
import os
import random
import shutil
import string
import subprocess
import json
import sys
import paramiko
import requests
import platform

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


def run_command(command, fail_on_failure=True, client=None):
    """
    Runs command either locally or on a remote machine via SSH
    :param command: Command that will be performed
    :param fail_on_failure: Flag if run should be terminated on failure or not
    :param client: Paramiko SSH client (optional)
    :return: output of command performed
    """
    try:
        logging.info(f"Executing command: {command}")
        if client:
            # Remote execution via SSH
            _stdin, stdout, _stderr = client.exec_command(command)
            stdout_result = stdout.read().decode('utf-8')
            stderr_result = _stderr.read().decode('utf-8')

            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0 and fail_on_failure:
                print(f"[ERROR] Remote command failed:\n{stderr_result}")
                raise Exception(stderr_result)

            return stdout_result, stderr_result
        else:
            # Local execution
            result = subprocess.run(command,
                                    shell=True,
                                    check=fail_on_failure,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    encoding='utf-8')
            if result.returncode != 0 and fail_on_failure:
                raise subprocess.CalledProcessError(result.returncode,
                                                    command,
                                                    output=result.stdout,
                                                    stderr=result.stderr)

            return result.stdout, result.stderr
    except subprocess.CalledProcessError as err:
        logging.error(f"Local command failed: {err.stderr}")
        print(f"[ERROR] Local command failed:\n{err.stderr}")
        if fail_on_failure:
            raise SystemExit(f"There was an issue running a command: {err}")
    except Exception as err:
        logging.error(f"Remote command failed: {err}")
        print(f"[ERROR] Remote command failed:\n{err}")
        if fail_on_failure:
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
    try:
        json_file = json.loads(file)
        logging.info("String was converted to JSON successfully!")
        return json_file
    except Exception as err:
        raise SystemExit(f"There was an error converting string to JSON format: {err}")

def connect_ssh(ip_address):
    SSH_HOST = ip_address
    SSH_USER = 'igor'
    SSH_KEY = None
    client = paramiko.SSHClient()
    try:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(SSH_HOST, username=SSH_USER, key_filename=SSH_KEY)
        return client
    except Exception as err:
        client.close()
        raise SystemExit("There was an issue connecting to host by ssh: {}".format(err))

def run_command_ssh(client, command):
    try:
        _stdin, stdout, _stderr = client.exec_command(command)
        for line in iter(lambda: stdout.readline(2048).rstrip(), ""):
            print(line)
        stderr = _stderr.read()
        if len(stderr) > 0:
            raise SystemExit(stderr)
    except Exception as err:
        raise SystemExit("There was an issue with ssh command: {}".format(err))


def get_target_dependency_path():
    """
    Gets home folder path of the user script is running from
    :return: String contains folder name
    """
    home_dir = os.path.expanduser("~")  # Getting home dir
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