
from .tellae_client import requests as tellae_requests, binaries, version
from qgis.core import (
    QgsApplication,
    QgsAuthMethodConfig,
    QgsProject,
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsVectorTileLayer,
    QgsMessageLog,
    QgsNetworkAccessManager,
)
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from .utils import log, AuthenticationError, read_local_config, RequestError
import os
import json


class TellaeStore:

    def __init__(self):
        # qgis network manager
        self.network_manager = QgsNetworkAccessManager.instance()

        # whale request manager
        self.whale_endpoint = "https://whale.tellae.fr"

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

    def authenticate(self, apikey, secret, endpoint=None):

        self.whale_endpoint = endpoint

        response = self.request_whale("/auth/me")

        # save user info
        self.user = response

        # tag store as authenticated
        self.authenticated = True

    def init_store(self):

        if not self.authenticated:
            raise AuthenticationError("User need to be authenticated before the store is initiated")

        self.request_layer_summary()
        self.request_datasets_summary()

        self.store_initiated = True

    def request_whale(self, url, method="GET", body=None):

        request = QNetworkRequest(QUrl(self.whale_endpoint + url))
        response = self.network_manager.blockingGet(request, authCfg="12hbli9")

        if response.error() == QNetworkReply.NoError:
            response_json = json.loads(bytes(response.content()))
        else:
            raise RequestError(response)

        return response_json

    def request_layer_summary(self):
        layers = self.request_whale("/shark/layers/table")

        layers = sorted(layers, key=lambda x: x["name"]["fr"])
        self.layer_summary = layers

        themes = list(set([theme for layer in layers for theme in layer["themes"]]))

        self.themes = sorted(themes)

    def request_datasets_summary(self):
        datasets = self.request_whale("/shark/datasets/summary")

        datasets = {dataset["id"]: dataset for dataset in datasets}

        self.datasets_summary = datasets

    def get_filtered_layer_summary(self, selected_theme: str):

        if selected_theme == "Tous":
            return self.layer_summary
        else:
            return [layer for layer in self.layer_summary if selected_theme in layer["themes"]]

    def vector_tile_url(self, table_id):

        full_url = self.whale_endpoint + "/martin/" + table_id + "/{z}/{x}/{y}".replace("{", "%7B").replace("}", "%7D")
        # headers = self.request_manager._get_headers(full_url, "GET", None, "application/json", None)
        # uri = f"url={full_url}&type=xyz&http-header:Authorization={headers['Authorization']}&http-header:Content-Type={headers['Content-Type']}"

        uri = f"url={full_url}&type=xyz&authcfg=12hbli9"

        log(uri)
        return uri


TELLAE_STORE = TellaeStore()