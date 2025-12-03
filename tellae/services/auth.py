from tellae.tellae_store import TELLAE_STORE
from tellae.utils import log
from tellae.utils.requests import request_whale, message_from_request_error
from tellae.services.project import select_project
from tellae.services.layers import init_layers_table
from qgis.core import (
    QgsApplication,
    QgsAuthMethodConfig,
)

# authentication constants

AWS_TELLAE_CONFIG = "AWS-Tellae"
AWS_TELLAE_DEV_CONFIG = "AWS-Tellae-dev"
AWS_TELLAE_TMP_CONFIG = "AWS-Tellae-tmp"
AWS_REGION = "fr-north-1"


# authentication actions

def init_auth():
    if (
            TELLAE_STORE.local_config is not None
            and "auth" in TELLAE_STORE.local_config
            and TELLAE_STORE.local_config["auth"].get("use", True)
    ):  # try dev authentication if provided and not deactivated
        _try_dev_indents()
        return

    # try to get existing auth config
    if not _try_existing_indents():
        log("No existing indents found, opening authentication dialog")
        # if no existing indents where found, show auth dialog to manually input new indents
        TELLAE_STORE.auth_dialog.change_page_and_show()


def try_new_indents(key, secret):
    # create a temporary config with new indents
    _create_or_update_auth_config(AWS_TELLAE_TMP_CONFIG, key, secret)

    def handler(_):
        # if the login was successful, remove temporary config and update main config
        remove_tellae_auth_config(AWS_TELLAE_TMP_CONFIG)
        _create_or_update_auth_config(AWS_TELLAE_CONFIG, key, secret)

    def on_error(_):
        # if the login failed, just remove the temporary config
        remove_tellae_auth_config(AWS_TELLAE_TMP_CONFIG)

    # try to login
    _login(handler=handler, error_handler=on_error)


def _try_dev_indents():
    # get indents from local config
    try:
        api_key = TELLAE_STORE.local_config["auth"]["apikey"]
        secret = TELLAE_STORE.local_config["auth"]["secret"]
    except KeyError as e:
        raise ValueError(f"Erreur lors de l'authentification locale, clé manquante: {str(e)}")

    # create or update DEV auth config
    _create_or_update_auth_config(AWS_TELLAE_DEV_CONFIG, api_key, secret)

    # try to login
    _login(set_indents=True)


def _try_existing_indents():
    # check for an existing auth config
    cfg_id = get_auth_config(AWS_TELLAE_CONFIG)

    if cfg_id is not None:
        # set auth config
        TELLAE_STORE.set_auth_config(AWS_TELLAE_CONFIG, cfg_id)

        # try to login
        _login(set_indents=True)

        return True

    return False


def _login(handler=None, error_handler=None, set_indents=False):
    # create full success callback
    def full_handler(result):
        # handler specific to login type
        if handler:
            handler(result)

        # actions that happen on successful login
        _on_login(result["content"])

        # set indents in auth dialog
        if set_indents:
            TELLAE_STORE.auth_dialog.set_indents_from_auth_config()

    def full_error_handler(result):
        if error_handler:
            error_handler(result)

        # display error message in auth dialog
        TELLAE_STORE.auth_dialog.display_error_message(message_from_request_error(result))
        # show authentication dialog
        TELLAE_STORE.auth_dialog.change_page_and_show()

    # make request to whale /auth/me service
    request_whale("/auth/me", handler=full_handler, error_handler=full_error_handler)


def _on_login(user):
    # update user in store (also tags store as authenticated)
    TELLAE_STORE.set_user(user)

    # update login button
    TELLAE_STORE.main_dialog.config_panel.set_auth_button_text(user)

    # update project list
    TELLAE_STORE.main_dialog.config_panel.fill_project_selector()

    # select project
    select_project(user["kite"]["project"])

    # if store is not initiated, do it now
    if not TELLAE_STORE.store_initiated:
        init_store()


def _create_or_update_auth_config(name, key, secret):
    auth_cfg = create_auth_config(name, key, secret)
    TELLAE_STORE.set_auth_config(name, auth_cfg)


# authentication utils

def create_auth_config(config_name, api_key, api_secret):
    config = None

    auth_manager = QgsApplication.authManager()
    config_dict = auth_manager.availableAuthMethodConfigs()
    for existing_config in config_dict.values():
        if existing_config.name() == config_name:
            config = existing_config

    if config is not None:
        config.setConfig("region", AWS_REGION)
        config.setConfig("username", api_key)
        config.setConfig("password", api_secret)
        auth_manager.updateAuthenticationConfig(config)
    else:
        auth_manager = QgsApplication.authManager()
        config = QgsAuthMethodConfig()
        config.setName(config_name)
        config.setMethod("AWSS3")
        config.setConfig("region", AWS_REGION)
        config.setConfig("username", api_key)
        config.setConfig("password", api_secret)
        auth_manager.storeAuthenticationConfig(config)

    return config.id()


def get_auth_config(config_name):
    auth_manager = QgsApplication.authManager()
    config_dict = auth_manager.availableAuthMethodConfigs()
    for config in config_dict.values():
        if config.name() == config_name:
            return config.id()
    return None


def remove_tellae_auth_config(cfg_name):
    auth_manager = QgsApplication.authManager()
    config_dict = auth_manager.availableAuthMethodConfigs()
    for authConfig in config_dict.keys():
        if config_dict[authConfig].name() == cfg_name:
            auth_manager.removeAuthenticationConfig(authConfig)
            break


def get_apikey_from_cache(cfg_name):
    auth_manager = QgsApplication.authManager()
    config_dict = auth_manager.availableAuthMethodConfigs()
    apikey = None
    secret = None
    for config in config_dict.values():
        if config.name() == cfg_name:
            aux_config = QgsAuthMethodConfig()
            auth_manager.loadAuthenticationConfig(config.id(), aux_config, True)
            apikey = aux_config.configMap()["username"]
            secret = aux_config.configMap()["password"]
    return apikey, secret


def init_store():
    """
    Initialise the plugin store with static data from Whale.
    """
    if not TELLAE_STORE.authenticated:
        log("Trying to initiate store without being authenticated")
        return

    init_layers_table()

    TELLAE_STORE.store_initiated = True