import logging
import os
from typing import Dict

import yaml

logger = logging.getLogger(__name__)


def _apply_int_override(params: Dict, env_name: str, path: tuple):
    raw = os.environ.get(env_name)
    if not raw:
        return
    value = int(raw)
    cursor = params
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    logger.info(f"{env_name} applied: {value}")


def load_params(config_file_path: str) -> Dict:
    logger.info(
        "\n----------------------------------- USED HYPERPARAMETERS -----------------------------------\n"
    )

    if not os.path.isfile(config_file_path):
        logger.error(f"Config file {config_file_path} does not exist!")
        raise FileNotFoundError

    try:
        with open(config_file_path, "rb") as config_file:
            params = yaml.load(config_file.read(), Loader=yaml.Loader)

        mission_type_override = os.environ.get("MISSION_TYPE_OVERRIDE")
        if mission_type_override:
            params["experiment"]["missions"]["type"] = mission_type_override
            logger.info(f"MISSION_TYPE_OVERRIDE applied: {mission_type_override}")

        _apply_int_override(
            params, "N_EPISODES_OVERRIDE", ("experiment", "missions", "n_episodes")
        )
        _apply_int_override(params, "BATCH_SIZE_OVERRIDE", ("networks", "batch_size"))
        _apply_int_override(
            params, "BATCH_NUMBER_OVERRIDE", ("networks", "batch_number")
        )
        _apply_int_override(params, "DATA_PASSES_OVERRIDE", ("networks", "data_passes"))

        logger.info(params)
        return params
    except Exception as e:
        logger.error(f"Error while reading config file! {e}")
        raise Exception(e)
