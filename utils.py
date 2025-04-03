import os
import json

def read_local_config():
    if os.path.exists("local.config.jsonc"):
        with open("local.config.jsonc", "r") as local_config:
            config = json.load(local_config)

        environment_variables = config.get("env", {})

        for k, v in environment_variables.items():
            os.environ[k] = v

        return True

    else:
        return False
