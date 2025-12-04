from tellae.utils.utils import (
    THEMES_TRANSLATION,
    log,
)
from tellae.utils.requests import request_whale, RequestsException
from tellae.tellae_store import TELLAE_STORE
from qgis.core import Qgis
import traceback


def init_layers_table():
    try:
        # get database layers table
        db_layers_table = request_whale("/shark/layers/table", blocking=True)["content"]

        # filter visible layers
        layers = [layer for layer in db_layers_table if layer["visible"]]

        # evaluate list of themes
        themes = list(set([theme for layer in layers for theme in layer["themes"]]))
        themes = [THEMES_TRANSLATION[theme] for theme in themes]

        # update store
        TELLAE_STORE.layer_summary = layers
        TELLAE_STORE.themes = sorted(themes)

        # get dataset table
        dataset_table = request_whale("/shark/datasets/summary", blocking=True)["content"]
        datasets = {dataset["id"]: dataset for dataset in dataset_table}

        TELLAE_STORE.datasets_summary = datasets

        # code that needs both tables to be set

        # sort layers table by name and date (desc)
        TELLAE_STORE.layer_summary = sorted(
            TELLAE_STORE.layer_summary,
            key=lambda x: (
                x["name"][TELLAE_STORE.locale],
                -int(TELLAE_STORE.datasets_summary[x["main_dataset"]].get("date", 0)),
            ),
        )

        # fill UI using results
        TELLAE_STORE.main_dialog.layers_panel.fill_theme_selector()
        TELLAE_STORE.main_dialog.layers_panel.fill_layers_table()
    except RequestsException as e:
        log(f"An error occurred while trying to database layer tables: {e}")

# layer download context manager

class LayerDownloadContext:

    def __init__(self, layer_name, handler, error_handler=None):

        self.layer_name = layer_name

        self.handler = self._evaluate_handler(handler)

        self.error_handler = self._evaluate_error_handler(error_handler)

    def _evaluate_handler(self, handler):
        return _layer_download_handler(handler)

    def _evaluate_error_handler(self, error_handler):
        return _layer_download_error_handler(self.layer_name, error_handler)

    def __enter__(self):
        # signal start of layer download
        _start_of_layer_download(self.layer_name)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return True
        else:
            # call handler if error occurred within context
            self.error_handler(exc_val)
            return False


def _layer_download_handler(handler):
    def final_handler(result):
        # signal end of download
        _end_of_layer_download()

        handler(result)

    return final_handler


def _layer_download_error_handler(layer_name, error_handler=None):
    def final_handler(result):
        log(f"Error while downloading '{layer_name}': {result['exception']}")
        log(result)
        TELLAE_STORE.main_dialog.display_message_bar(
            f"Erreur lors du téléchargement de la couche '{layer_name}': {result['status_code']} ({result['status_message']})",
            level=Qgis.MessageLevel.Critical
        )

        _end_of_layer_download()

        if error_handler is not None:
            error_handler(result)

    return final_handler


def _start_of_layer_download(layer_name):
    TELLAE_STORE.main_dialog.start_progress(f"Téléchargement de la couche '{layer_name}' ...")


def _end_of_layer_download():
    # stop progress bar
    TELLAE_STORE.main_dialog.end_progress()



