from tellae.utils.utils import (
    read_local_config,
    THEMES_TRANSLATION,
)
import os


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

        # current project
        self.current_project = None

        # full layer summary
        self.layer_summary = []

        self.themes = []

        # data datasets summary
        self.datasets_summary = {}

        # number of custom layers
        self.nb_custom_layers = 0

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
        self.projects_dialog = None

    @property
    def current_project_name(self):
        if self.current_project is None:
            return ""
        else:
            return self.current_project.get("name", "Main")

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

    def set_dialogs(self, tellae_services):
        self.tellae_services = tellae_services
        self.main_dialog = tellae_services.dlg
        self.auth_dialog = tellae_services.auth
        self.projects_dialog = tellae_services.projects_dlg


    def get_filtered_layer_summary(self, selected_theme: str):

        if selected_theme == "Tous":
            return self.layer_summary
        else:
            return [
                layer
                for layer in self.layer_summary
                if selected_theme in [THEMES_TRANSLATION[theme] for theme in layer["themes"]]
            ]

    def increment_nb_custom_layers(self):
        self.nb_custom_layers += 1

    # AUTHENTICATION methods

    def set_user(self, user):
        self.user = user
        self.authenticated = True

    def set_auth_config(self, cfg_name, cfg_id):
        self.authCfg = cfg_id
        self.authName = cfg_name

    # PROJECTS ACTIONS

    def set_current_project(self, project):
        self.current_project = project

    # map utils

    def get_current_scale(self):
        return self.tellae_services.iface.mapCanvas().scale()



TELLAE_STORE = TellaeStore()
