
from .tellae_client import requests, binaries, version
from qgis.core import (
    QgsApplication,
    QgsAuthMethodConfig,
    QgsProject,
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsVectorTileLayer,
    QgsMessageLog,
)
from .utils import log
import urllib.parse


class TellaeStore:

    def __init__(self):
        # whale request manager
        self.request_manager = requests.ApiKeyRequestManager()

        # stored objects

        self.user = {}

        # full layer summary
        self.layer_summary = []

        self.themes = []

        # data datasets summary
        self.datasets_summary = {}

        # call some initialisation requests
        self.request_layer_summary()
        self.request_datasets_summary()
        self.request_auth_me()

    def request_auth_me(self):
        self.user = self.request_manager.request("/auth/me").json()

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

    def get_filtered_layer_summary(self, selected_themes: list):

        if len(selected_themes) == 0:
            return self.layer_summary
        else:
            return [layer for layer in self.layer_summary if (set(selected_themes) & set(layer["themes"]))]

    def vector_tile_url(self, table_id):

        full_url = self.request_manager.whale_endpoint + "/martin/" + table_id + "/{z}/{x}/{y}".replace("{", "%7B").replace("}", "%7D")
        headers = self.request_manager._get_headers(full_url, "GET", None, "application/json", None)

        uri = f"url={full_url}&type=xyz&http-header:Authorization={headers['Authorization']}&http-header:Content-Type={headers['Content-Type']}"
        log(uri)
        return uri


