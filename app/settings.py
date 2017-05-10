import logging
import os

from easydict import EasyDict
import yaml


path = os.path.dirname(__file__)


def _load_config_file():
    try:
        with open("{}/../config/config.yaml".format(path)) as file:
            yaml_config = yaml.load(file)
    except:
        raise
    return EasyDict(yaml_config)


def configure_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler("{}/../logs/app.log".format(path))
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger

config = _load_config_file()


