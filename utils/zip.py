import logging
import platform
import zipfile

import config
from utils.utils import convert_to_json, clear_folder, run_command, get_os_platform


def get_zip_folder_name(image_list):
    """
    Gets folder name where dependency zip should be located. Name depends on version.
    :param image_list: List of images to be parsed
    :return: String containing folder name
    """
    if isinstance(image_list, str):
        image_list = convert_to_json(image_list)

    for item in image_list["related_images"]:
        for key, value in item.items():
            if "mta-cli-rhel9" in key:
                _, major, minor = value["nvr"].rsplit("-", 2)
                return f"MTA-{major}-{minor}"

def get_zip_name(version="upstream"):
    """
    Gets ZIP filename according to OS and CPU type
    :param version: MTA version, for example 7.2.0 or 7.1.1
    :return: String containing file name
    """
    os_name, machine = get_os_platform()

    if version != "upstream":
        zip_name = f"mta-{version}-cli-{os_name}-{machine}.zip"
        logging.info(f"Expecting {zip_name} to be available...")
    else:
        zip_name = f"kantra.{os_name}.{machine}.zip"
        logging.info(f"Expecting {zip_name} to be available...")

    return zip_name


def unpack_zip(zip_file, target_path):
    """
    Unpacks a ZIP file into the specified target directory.
    :param zip_file: Path to the ZIP file to be unpacked.
    :param target_path: Directory where the contents of the ZIP file will be extracted.
    """
    clear_folder(target_path)

    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        try:
            zip_ref.extractall(target_path)
            logging.info(f"Zip {zip_file} unpacked successfully to {target_path}")
        except Exception as err:
            raise SystemExit("There was an issue with unpacking zip file: {}".format(err))


def generate_zip(version, build):
    """Generates zip with dependencies for local run"""
    extract_binary_command = f"{config.MISC_DOWNSTREAM_PATH}{config.EXTRACT_BINARY} {config.BUNDLE}{version}-{build} {config.NO_BREW}"
    run_command(extract_binary_command)
