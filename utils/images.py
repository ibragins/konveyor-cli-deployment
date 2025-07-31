import logging
import subprocess

import config
from utils.const import related_images, repositories, basic_images
from utils.utils import run_command, convert_to_json


def pull_tag_images(mta_version, output_file, client=None):
    """
    Pulls and tags images from the list it gets
    :param mta_version: MTA version to be deployed
    :param output_file: Output with list of images to be pulled. Can be generated and forwarded here or provided as CLI parameter
    :param client: SSH client, optional parameter. Will be used to connect to remote host and pull images there if present.
    """
    related_images = convert_to_json(output_file).get('related_images_pullspecs', None)
    required_version_tuple = (7, 3, 0)
    current_version_tuple = tuple(map(int, mta_version.split('.')))
    if related_images:  # If related images are present then proceed
        keywords = ['java', 'generic', 'dotnet', 'cli']
        for image in related_images:
            if any(keyword in image for keyword in keywords):  # Check if the image contains any of the keywords.
                logging.info(f"Image : {image}")
                # Pull image from registry-proxy.engineer.redhat.com
                proxy_image_url = 'brew.registry.redhat.io/rh-osbs/mta-{}'.format(image.split('/')[-1])
                pull_command = f'podman pull {proxy_image_url} --tls-verify=false'
                logging.info(f'Pulling image: {proxy_image_url}')
                run_command(pull_command, True, client)
                logging.info('Pull successful')
                tag_image = image.split('@sha')[-2]
                if 'dotnet' in tag_image and current_version_tuple < required_version_tuple :
                    tag_image = tag_image.replace("rhel9", "rhel8")
                logging.info(f'Tagging image {proxy_image_url} to {tag_image}:{mta_version}')
                tag_command = f'podman tag {proxy_image_url} {tag_image}:{mta_version}'  #Tag image to correct version
                run_command(tag_command, True, client)
                logging.info(f'Tagging {image} is completed...')


def pull_stage_ga_images(mta_version, repo):
    """
    Pulls images for Stage / GA
    :param mta_version: MTA version to be pulled
    :param repo: either ga or stage to be pulled
    :return:
    """
    required_version_tuple = (7, 3, 0)
    current_version_tuple = tuple(map(int, mta_version.split('.')))
    images = basic_images + related_images

    for image in images:
        if 'dotnet' in image and current_version_tuple < required_version_tuple:
            image = image.replace("rhel9", "rhel8")
        image_url = repositories.get(repo) + f'/mta/{image}:{mta_version}'
        logging.info(f"Processing repository: {repo} (url: {image_url})")
        # Pull the image
        pull_command = f"podman pull {image_url} --tls-verify=false"
        run_command(pull_command)
        logging.info(f"Pulled image from {repo}")
        # Tag the image based on the repository type
        tag_command = f"podman tag {image_url} {repositories.get('ga') + f'/mta/{image}:{mta_version}'}"
        if repo != 'ga' and repo != 'candidate':
            run_command(tag_command)
            logging.info(f"Tagged image {image} to ga")


def remove_old_images(version="upstream", client=None):
    """
    Removes old images before pulling new
    :param version: MTA version to be cleaned up
    :param client: SSH client, optional parameter to run cleanup remotely
    """
    try:
        result, result_err = run_command("podman images", client=client)

        # Filtering lines that contain "registry" and version
        images = []

        for line in result.splitlines():  # result is already a string
            columns = line.split()
            if "registry" in line and version in line:
                # Third column - IMAGE ID
                if len(columns) >= 3:
                    images.append(columns[2])

        # Deleting images gotten after filtering
        for image in images:
            run_command(f"podman rmi {image} --force", client=client)
            logging.info(f"Image {image} was removed successfully")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error while performing command: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


def generate_images_list(version, build):
    """
    Generates list of images and pulls them
    :param version: MTA version, for example 7.2.0
    :param build: build number
    :return: String containing list of images. Can be converted to JSON after that.
    """
    get_images_output_command = f'cd {config.MISC_DOWNSTREAM_PATH}; ./{config.GET_IMAGES_OUTPUT}{config.BUNDLE}{version}-{build}'
    return run_command(get_images_output_command)