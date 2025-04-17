
from .tellae_client import requests as tellae_requests, binaries, version
from qgis.core import (
    QgsApplication,
    QgsAuthMethodConfig,
    QgsProject,
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsVectorTileLayer,
    QgsMessageLog,
)
from .utils import log, AuthenticationError, read_local_config
import urllib.parse
import os
import requests


class TellaeStore:

    def __init__(self):
        log("Create TellaeStore")
        # whale request manager
        self.request_manager = None

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

    def read_local_config(self):
        # store local configuration
        self.local_config = read_local_config(self.plugin_dir)

        # TODO: put the function and this call somewhere else
        self.remove_auth_environment()

        if self.local_config is not None:
            log(str(self.local_config))
            # setup environment variables from local config
            environment_variables = self.local_config.get("env", {})
            for k, v in environment_variables.items():
                log(k)
                os.environ[k] = v

    def remove_auth_environment(self):
        for var in ["WHALE_API_KEY_ID", "WHALE_SECRET_ACCESS_KEY", "WHALE_ENDPOINT"]:
            if var in os.environ:
                os.environ.pop(var)
    def authenticate(self):
        try:
            # request manager instance
            self.request_manager = tellae_requests.ApiKeyRequestManager()

            # call some initialisation requests
            self.request_auth_me()

            # tag store as authenticated
            self.authenticated = True

        except (EnvironmentError, AuthenticationError) as e:
            self.authenticated = False
            raise e

    def init_store(self):

        if not self.authenticated:
            raise AuthenticationError("User need to be authenticated before the store is initiated")

        self.request_layer_summary()
        self.request_datasets_summary()

        self.store_initiated = True

    def request_auth_me(self):

        response = self.request_manager.request("/auth/me", raise_exception=False)

        if 200 <= response.status_code < 300:
            self.user = response.json()
        elif response.status_code in [401, 403]:
            raise AuthenticationError
        else:
            raise ValueError(response.status_code)

    def request_layer_summary(self):
        layers = self.request_manager.shark("/layers/table").json()
        layers = sorted(layers, key=lambda x: x["name"]["fr"])
        self.layer_summary = layers

        themes = list(set([theme for layer in layers for theme in layer["themes"]]))

        self.themes = sorted(themes)

    def request_datasets_summary(self):
        datasets = self.request_manager.shark("/datasets/summary").json()

        datasets = {dataset["id"]: dataset for dataset in datasets}

        self.datasets_summary = datasets

    def get_filtered_layer_summary(self, selected_theme: str):

        if selected_theme == "Tous":
            return self.layer_summary
        else:
            return [layer for layer in self.layer_summary if selected_theme in layer["themes"]]

    def vector_tile_url(self, table_id):

        full_url = self.request_manager.whale_endpoint + "/martin/" + table_id + "/{z}/{x}/{y}".replace("{", "%7B").replace("}", "%7D")
        headers = self.request_manager._get_headers(full_url, "GET", None, "application/json", None)

        uri = f"url={full_url}&type=xyz&http-header:Authorization={headers['Authorization']}&http-header:Content-Type={headers['Content-Type']}"
        log(uri)
        return uri


TELLAE_STORE = TellaeStore()