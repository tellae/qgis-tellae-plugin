import os
import json

import tempfile


import requests
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QCoreApplication, QElapsedTimer
from qgis.core import (
    QgsApplication,
    QgsAuthMethodConfig,
    QgsProject,
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsVectorTileLayer,
    QgsMessageLog,
)

def log(message):
    QgsMessageLog.logMessage(str(message), "TellaeServices")

def read_local_config(plugin_dir):
    config = None
    path = plugin_dir + "/local.config.jsonc"
    if os.path.exists(path):
        with open(path, "r") as local_config:
            config = json.load(local_config)

    return config


class CancelImportDialog(QtWidgets.QDialog):
    def __init__(self):
        super(CancelImportDialog, self).__init__()
        ui_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = os.path.join(ui_dir, "cancel_import.ui")
        uic.loadUi(ui_path, self)

        self.isCanceled = False
        self.cancelButton.clicked.connect(self.cancelImport)

        self.show()

    def cancelImport(self):
        self.isCanceled = True


def create_layer_instance(layer_id, layer_stream, path=""):


    cancel_import_dialog = CancelImportDialog()
    try:
        file_path = path
        if file_path == "":
            file = tempfile.NamedTemporaryFile(suffix=".geojson")
            file.close()
            file_path = file.name
        downloaded = 0
        timer = QElapsedTimer()
        timer.start()
        with open(file_path, "wb") as f:
            for chunk in layer_stream.iter_content(chunk_size=1024 * 64):
                f.write(chunk)
                downloaded += len(chunk)
                QCoreApplication.processEvents()
                if timer.elapsed() > 0:
                    cancel_import_dialog.chunkLabel.setText(
                        "Downloaded: {}MB\nSpeed: {:.2f}kB/s".format(
                            downloaded // 1024 // 1024,
                            (downloaded / 1024) / (timer.elapsed() / 1000),
                        )
                    )
                if cancel_import_dialog.isCanceled:
                    return

    except FileNotFoundError:
        raise FileNotFoundError
    except PermissionError:
        raise PermissionError

    vector_layer = QgsVectorLayer(file_path, layer_id, "ogr")

    return vector_layer



def create_vector_layer_instance(layer_name, url):



    return QgsVectorTileLayer(url, layer_name)

def create_new_tellae_auth_config(api_key, api_secret):

    auth_manager = QgsApplication.authManager()
    config = QgsAuthMethodConfig()
    config.setName("tellae-cache")
    config.setMethod("APIHeader")
    config.setConfig("key", api_key)
    config.setConfig("secret", api_secret)
    auth_manager.storeAuthenticationConfig(config)


def remove_tellae_auth_config():
    auth_manager = QgsApplication.authManager()
    config_dict = auth_manager.availableAuthMethodConfigs()
    for authConfig in config_dict.keys():
        if config_dict[authConfig].name() == "tellae-cache":
            auth_manager.removeAuthenticationConfig(authConfig)
            break

def get_apikey_from_cache():
    auth_manager = QgsApplication.authManager()
    config_dict = auth_manager.availableAuthMethodConfigs()
    apikey = None
    secret = None
    for config in config_dict.values():
        if config.name() == "tellae-cache":
            aux_config = QgsAuthMethodConfig()
            auth_manager.loadAuthenticationConfig(config.id(), aux_config, True)
            apikey = aux_config.configMap()["key"]
            secret = aux_config.configMap()["secret"]
    return apikey, secret


class AuthenticationError(Exception):
    pass


class AccessError(Exception):
    pass


class InternalError(Exception):
    pass