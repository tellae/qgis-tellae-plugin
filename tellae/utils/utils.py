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
    QgsSymbolLayer,
    QgsSymbol,
    QgsProperty,
    QgsCategorizedSymbolRenderer,
    QgsRuleBasedRenderer,
    QgsRendererCategory,
    QgsSingleSymbolRenderer,
    QgsNetworkReplyContent,
)
from qgis.PyQt.QtWidgets import QTableWidgetItem, QTableWidget

AWS_REGION = "fr-north-1"

THEMES_TRANSLATION = {
    "carpooling": "Covoiturage",
    "demography": "Démographie",
    "employment": "Emploi",
    "rail": "Ferroviaire",
    "schooling": "Formation",
    "travel_generators": "Générateurs de déplacements",
    "mobility": "Mobilités",
    "land_use": "Occupation du sol",
    "income": "Revenus et niveau de vie",
    "public_transport": "Transports publics",
    "zoning": "Zonages et périmètres",
    "car_sharing": "Autopartage",
    "bike": "Vélo",
    "car": "Voiture",
    "walk": "Piéton",
}


def log(message):
    QgsMessageLog.logMessage(str(message), "TellaeServices")


def read_local_config(plugin_dir):
    config = None
    path = plugin_dir + "/local.config.json"
    if os.path.exists(path):
        with open(path, "r") as local_config:
            config = json.load(local_config)

    return config


# def create_layer_instance(layer_id, layer_stream, path=""):
#     try:
#         file_path = path
#         if file_path == "":
#             file = tempfile.NamedTemporaryFile(suffix=".geojson")
#             file.close()
#             file_path = file.name
#         with open(file_path, "wb") as f:
#             f.write(layer_stream)
#     except FileNotFoundError:
#         raise FileNotFoundError
#     except PermissionError:
#         raise PermissionError
#
#     vector_layer = QgsVectorLayer(file_path, layer_id, "ogr")
#
#     return vector_layer
#
#
#
#
#     cancel_import_dialog = CancelImportDialog()
#     try:
#         file_path = path
#         if file_path == "":
#             file = tempfile.NamedTemporaryFile(suffix=".geojson")
#             file.close()
#             file_path = file.name
#         downloaded = 0
#         timer = QElapsedTimer()
#         timer.start()
#         with open(file_path, "wb") as f:
#             for chunk in layer_stream.iter_content(chunk_size=1024 * 64):
#                 f.write(chunk)
#                 downloaded += len(chunk)
#                 QCoreApplication.processEvents()
#                 if timer.elapsed() > 0:
#                     cancel_import_dialog.chunkLabel.setText(
#                         "Downloaded: {}MB\nSpeed: {:.2f}kB/s".format(
#                             downloaded // 1024 // 1024,
#                             (downloaded / 1024) / (timer.elapsed() / 1000),
#                         )
#                     )
#                 if cancel_import_dialog.isCanceled:
#                     return
#
#     except FileNotFoundError:
#         raise FileNotFoundError
#     except PermissionError:
#         raise PermissionError
#
#     vector_layer = QgsVectorLayer(file_path, layer_id, "ogr")
#
#     return vector_layer
#
#
#
# def create_vector_layer_instance(layer_name, url):
#
#     return QgsVectorTileLayer(url, layer_name)


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


def fill_table_widget(table_widget, headers, items):
    # disable table edition
    table_widget.setEditTriggers(QTableWidget.NoEditTriggers)

    # set number of rows and columns
    table_widget.setRowCount(len(items))
    table_widget.setColumnCount(len(headers))

    # setup headers
    table_widget.setHorizontalHeaderLabels([header["text"] for header in headers])
    for col, header in enumerate(headers):
        if "width" in header:
            table_widget.setColumnWidth(col, header["width"])

    # populate table cells
    for row, layer in enumerate(items):
        for col, header in enumerate(headers):
            # create a table cell
            cell = QTableWidgetItem()

            # evaluate its content depending on the row and column
            if "slot" in header:
                header["slot"](table_widget, row, col, layer, header)
                continue
            elif callable(header["value"]):
                text = header["value"](layer)
            else:
                text = layer[header["value"]]

            # set cell text and tooltip
            cell.setText(text)
            cell.setToolTip(text)

            # set text alignment
            if "align" in header:
                cell.setTextAlignment(header["align"])

            # put the cell in the table
            table_widget.setItem(row, col, cell)


def getBinaryName(binary, with_extension=True):
    if "metadata" in binary and "name" in binary["metadata"]:
        name = binary["metadata"]["name"]
    elif "name" in binary:
        name = binary["name"]
    else:
        name = binary.get("originalname", "Unnamed")

    if not with_extension:
        name = name.split(".")[0]

    return name

# def prepare_layer_style(layer, layer_info):
#
#     renderer = layer.renderer()
#
#     additional_properties = layer_info.get("additionalProperties", {})
#     if "editAttributes" in additional_properties:
#         log(str(additional_properties["editAttributes"]["color"]))
#         renderer = set_color_edit_attribute(layer, additional_properties["editAttributes"]["color"])
#         # set_edit_attributes(renderer, additional_properties["editAttributes"])
#
#     layer.setRenderer(renderer)  # necessary to emit rendererChanged signal (updates Layer Styling panel)
#
#
# def set_edit_attributes(layer, edit_attributes):
#     for key, props_mapping in edit_attributes.items():
#         if key == "color":
#             set_color_edit_attribute(layer, props_mapping)
#
#
# def set_color_edit_attribute(layer, color_props_mapping):
#     # get props_mapping type
#     mapping_type = color_props_mapping["type"]
#
#     mapping_options = color_props_mapping.get("mapping_options", color_props_mapping.get("mapping_data"))
#
#     log(layer.renderer().__class__.__name__)
#
#     if mapping_type == "constant":
#         pass
#     elif mapping_type == "direct":
#         renderer = layer.renderer()
#
#         color_attribute = mapping_options["key"]
#         expression = f'prefixed_color("{color_attribute}")'
#
#         renderer.symbol().symbolLayer(0).setDataDefinedProperty(
#             infer_color_property(renderer),
#             QgsProperty.fromExpression(expression)
#         )
#
#         # renderer = QgsSingleSymbolRenderer.convertFromRenderer(layer.renderer())
#         # symbol = QgsSymbol.defaultSymbol(layer.geometryType())
#         # log(symbol.__class__.__name__)
#         # symbol.setDataDefinedProperty(
#         #     infer_color_property(layer),
#         #     QgsProperty.fromExpression(expression)
#         # )
#         # renderer.setSymbol(symbol)
#
#     elif mapping_type == "category":
#
#         values_labels = mapping_options.get("values_labels", {})
#         for key, color in mapping_options["values_map"].items():
#             symbol = QgsSymbol.defaultSymbol(layer.geometryType())
#             symbol.setColor(color)
#
#             category = QgsRendererCategory(key, symbol, values_labels.get(key, key))
#             # renderer.addCategory(category)
#
#
#     elif mapping_type == "continuous":
#         raise NotImplementedError
#     else:
#         raise ValueError("Unknown mapping type")
#
#     return renderer
#
#
# def infer_color_property(layer):
#     return QgsSymbolLayer.PropertyStrokeColor
