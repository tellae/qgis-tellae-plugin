
from .tellae_client import requests, binaries, version
from qgis.core import (
    QgsMessageLog,
)

class TellaeStore:

    def __init__(self):
        # whale request manager
        self.request_manager = requests.ApiKeyRequestManager()

        # stored objects

        self.user = {}

        # full layer summary
        self.layer_summary = []

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

    def request_datasets_summary(self):
        datasets = self.request_manager.shark("/datasets/summary").json()

        datasets = {dataset["id"]: dataset for dataset in datasets}

        self.datasets_summary = datasets

    def get_filtered_layer_summary(self):
        return self.layer_summary

    def log(self, message):
        QgsMessageLog.logMessage(message, "TellaeServices")