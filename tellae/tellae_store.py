from tellae.utils.utils import (
    log,
    read_local_config,
    get_apikey_from_cache,
    create_auth_config,
    get_auth_config,
    remove_tellae_auth_config,
    THEMES_TRANSLATION,
)
from tellae.utils.network_access_manager import NetworkAccessManager
import os
import json

AWS_TELLAE_CONFIG = "AWS-Tellae"
AWS_TELLAE_DEV_CONFIG = "AWS-Tellae-dev"
AWS_TELLAE_TMP_CONFIG = "AWS-Tellae-tmp"


class TellaeStore:

    def __init__(self):

        # whale request manager
        self.whale_endpoint = "https://whale.tellae.fr"

        self.request_retries = dict()

        # locale (translations)
        self.locale = "fr"

        # authentication

        self.authCfg = None
        self.authName = None

        self.authenticated = False

        self.store_initiated = False

        # plugin data
        self.plugin_dir = os.path.dirname(__file__)

        # stored objects

        # authenticated user
        self.user = {}

        # full layer summary
        self.layer_summary = []

        self.themes = []

        # data datasets summary
        self.datasets_summary = {}

        # local config
        self.local_config = None
        self.read_local_config()
        self.network_debug = (
            False if self.local_config is None else self.local_config.get("network_debug", False)
        )

        # plugin dialogs
        self.tellae_services = None
        self.main_dialog = None
        self.auth_dialog = None

    def read_local_config(self):
        # read local config
        local_config = read_local_config(self.plugin_dir)

        # store local configuration if "use" is True
        if local_config is not None and local_config.get("use", True):
            self.local_config = local_config

        # set store attributes from local config
        if self.local_config and "whale_endpoint" in self.local_config:
            self.whale_endpoint = self.local_config["whale_endpoint"]

    # STORE ACTIONS

    def init_store(self):
        if not self.authenticated:
            log("Trying to initiate store without being authenticated")
            return

        self._init_layers_table()

        self.store_initiated = True

    def _init_layers_table(self):

        def common_handler():
            # sort layers table by name and date (desc)
            self.layer_summary = sorted(self.layer_summary, key=lambda x: (x["name"]["fr"], -int(self.datasets_summary[x["main_dataset"]].get("date", 0))))

            # fill UI using results
            self.main_dialog.create_theme_selector()
            self.main_dialog.set_layers_table()

        def layer_summary_handler(response):
            result = response["content"]
            # filter visible layers
            layers = [layer for layer in result if layer["visible"]]

            # evaluate list of themes
            themes = list(set([theme for layer in layers for theme in layer["themes"]]))
            themes = [THEMES_TRANSLATION[theme] for theme in themes]

            # update store
            self.layer_summary = layers
            self.themes = sorted(themes)

            if self.layer_summary and self.datasets_summary:
                common_handler()

        self.request_whale("/shark/layers/table", handler=layer_summary_handler)

        def datasets_summary_handler(response):
            result = response["content"]
            datasets = {dataset["id"]: dataset for dataset in result}

            self.datasets_summary = datasets

            if self.layer_summary and self.datasets_summary:
                common_handler()

        self.request_whale("/shark/datasets/summary", handler=datasets_summary_handler)

    def get_filtered_layer_summary(self, selected_theme: str):

        if selected_theme == "Tous":
            return self.layer_summary
        else:
            return [
                layer
                for layer in self.layer_summary
                if selected_theme in [THEMES_TRANSLATION[theme] for theme in layer["themes"]]
            ]

    # AUTHENTICATION methods

    def init_auth(self):
        if (
            self.local_config is not None
            and "auth" in self.local_config
            and self.local_config["auth"].get("use", True)
        ):  # try dev authentication if provided and not deactivated
            self._try_dev_indents()
            return

        # try to get existing auth config
        if not self._try_existing_indents():
            log("No existing indents found, opening authentication dialog")
            # if no existing indents where found, show auth dialog to manually input new indents
            self.auth_dialog.show()

    def try_new_indents(self, key, secret):

        # create a temporary config with new indents
        self._create_or_update_auth_config(AWS_TELLAE_TMP_CONFIG, key, secret)

        def handler(_):
            # if the login was successful, remove temporary config and update main config
            remove_tellae_auth_config(AWS_TELLAE_TMP_CONFIG)
            self._create_or_update_auth_config(AWS_TELLAE_CONFIG, key, secret)

        def on_error(_):
            # if the login failed, just remove the temporary config
            remove_tellae_auth_config(AWS_TELLAE_TMP_CONFIG)

        # try to login
        self._login(handler=handler, error_handler=on_error)

    def get_current_indents(self):
        return get_apikey_from_cache(self.authName)

    def _try_dev_indents(self):
        # get indents from local config
        try:
            api_key = self.local_config["auth"]["apikey"]
            secret = self.local_config["auth"]["secret"]
        except KeyError as e:
            raise ValueError(f"Erreur lors de l'authentification locale, clé manquante: {str(e)}")

        # create or update DEV auth config
        self._create_or_update_auth_config(AWS_TELLAE_DEV_CONFIG, api_key, secret)

        # try to login
        self._login(set_indents=True)

    def _try_existing_indents(self):
        # check for an existing auth config
        cfg_id = get_auth_config(AWS_TELLAE_CONFIG)

        if cfg_id is not None:
            # set auth config
            self._set_auth_config(AWS_TELLAE_CONFIG, cfg_id)

            # try to login
            self._login(set_indents=True)

            return True

        return False

    def _login(self, handler=None, error_handler=None, set_indents=False):

        # create full success callback
        def full_handler(result):
            if handler:
                handler(result)

            # set user in store
            self.user = result["content"]

            # update login button
            self.main_dialog.set_auth_button_text(self.user)

            # tag store as authenticated
            self.authenticated = True

            # if store is not initiated, do it now
            if not self.store_initiated:
                self.init_store()

            if set_indents:
                self.auth_dialog.set_indents_from_auth_config()

        def full_error_handler(result):
            if error_handler:
                error_handler(result)

            # display error message in auth dialog
            self.auth_dialog.display_error_message(message_from_request_error(result))
            # show authentication dialog
            self.auth_dialog.open()

        # make request to whale /auth/me service
        self.request_whale("/auth/me", handler=full_handler, error_handler=full_error_handler)

    def _create_or_update_auth_config(self, name, key, secret):
        auth_cfg = create_auth_config(name, key, secret)
        self._set_auth_config(name, auth_cfg)

    def _set_auth_config(self, cfg_name, cfg_id):
        self.authCfg = cfg_id
        self.authName = cfg_name

    # NETWORK REQUESTS METHODS

    def request(
        self,
        url,
        method="GET",
        body=None,
        handler=None,
        error_handler=None,
        auth_cfg=None,
        to_json=True,
    ):

        # create a network access manager instance
        nam = NetworkAccessManager(authid=auth_cfg, debug=self.network_debug, timeout=0)

        # create callback function: call handler depending on request success
        def on_finished():

            result = nam.httpResult()
            if result["ok"] and handler:
                if url in self.request_retries:
                    del self.request_retries[url]
                # convert request result to json
                if to_json:
                    result["content"] = json.loads(result["content"])
                handler(result)
            elif not result["ok"] and result["status_code"] == 401:
                if url in self.request_retries:
                    self.request_retries[url] += 1
                else:
                    self.request_retries[url] = 1

                log(
                    f"Requesting {url} failed with error 401, total: {self.request_retries[url]} fails"
                )

                if self.request_retries[url] < 3:
                    log(f"Retry requesting {url}")
                    self.request(url, method, body, handler, error_handler, auth_cfg, to_json)
                else:
                    if error_handler:
                        error_handler(result)

            elif not result["ok"] and error_handler:
                error_handler(result)

        try:
            # make async request
            nam.request(url, method=method, body=body, blocking=False)

            # add callback
            nam.reply.finished.connect(on_finished)
        except Exception as e:
            # call error handler on exception
            if error_handler:
                error_handler(
                    {
                        "status": None,
                        "status_code": None,
                        "status_message": "Python error while making request",
                        "content": None,
                        "ok": False,
                        "headers": None,
                        "reason": "Python error while making request",
                        "exception": e,
                    }
                )

    def request_whale(self, url, **kwargs):
        if url.startswith("https://"):
            raise ValueError("Only the relative path of the Whale url should be provided")

        # prepend whale endpoint
        whale_url = self.whale_endpoint + url

        # make the request using the AWS authentication
        return self.request(whale_url, auth_cfg=self.authCfg, **kwargs)

    # map utils

    def get_current_scale(self):
        return self.tellae_services.iface.mapCanvas().scale()


def message_from_request_error(result):
    status = result["status"]
    status_code = result["status_code"]
    status_message = result["status_message"]
    reason = result["reason"]
    return str(result["exception"])


TELLAE_STORE = TellaeStore()
