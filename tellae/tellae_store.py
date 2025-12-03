from tellae.utils.utils import (
    read_local_config,
    THEMES_TRANSLATION,
    log,
    getBinaryName
)
import os
from enum import IntEnum


class TellaeStore:

    # tab values enumeration (number corresponds to page number)
    class Tabs(IntEnum):
        layers = 0
        config = 1
        about = 2

    def __init__(self):

        # whale request manager
        self.whale_endpoint = "https://whale.tellae.fr"

        self.request_retries = dict()

        # locale (translations)
        self.locale = "fr"

        # UX variables

        self.tab = None

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

    @property
    def current_project_name(self):
        if self.current_project is None:
            return ""
        else:
            return self.current_project.get("name", "Mon projet")

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


    def get_filtered_layer_summary(self, selected_theme: str):

        if selected_theme == "Tous":
            return self.layer_summary
        else:
            return [
                layer
                for layer in self.layer_summary
                if selected_theme in [THEMES_TRANSLATION[theme] for theme in layer["themes"]]
            ]

    def get_project_data(self, attribute):
        """
        Get the sorted list of binaries for the given attribute.

        :param attribute: project property, one of ["spatial_data", "flows", "gtfs"]

        :return: sorted list of binaries
        """
        data = self.current_project[attribute]

        sorted_data = sorted(
            data,
            key=lambda x: getBinaryName(x, with_extension=False),
        )

        return sorted_data


    def increment_nb_custom_layers(self):
        self.nb_custom_layers += 1

    def set_tab(self, index_or_name, update_menu_widget=False):
        if isinstance(index_or_name, int):
            index = index_or_name
            name = self.Tabs(index_or_name)
        elif isinstance(index_or_name, self.Tabs):
            index = index_or_name.value
            name = index_or_name
        else:
            raise ValueError("Unknown tab value")

        # update widgets
        if update_menu_widget:
            self.main_dialog.menu_widget.setCurrentRow(index)
        self.main_dialog.stacked_panels_widget.setCurrentIndex(index)

        # update store
        self.tab = name

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
