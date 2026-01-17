from tellae.utils.utils import (
    THEMES_TRANSLATION,
    log,
)
from tellae.utils.requests import RequestsException
from tellae.models.layers import (
    QgsKiteLayer,
    LayerInitialisationError,
    LayerStylingException,
    MinZoomException,
    EmptyLayerException,
)
from tellae.utils.requests import request_whale
from tellae.tellae_store import TELLAE_STORE
from qgis.core import (
    Qgis,
)
import traceback


def init_layers_table():
    try:
        # get database layers table
        db_layers_table = request_whale("/shark/layers/table", blocking=True)["content"]

        # filter visible layers
        layers = [layer for layer in db_layers_table if layer["visible"]]

        # evaluate list of themes
        themes = list(set([theme for layer in layers for theme in layer["themes"]]))
        themes = [THEMES_TRANSLATION.get(theme, theme) for theme in themes]

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
    except Exception as e:
        raise ValueError("Erreur lors de la récupération de la table des calques") from e


def signal_layer_add_error(layer_name, exception):
    """
    Signal that an error was encountered while creating the layer or adding it to Qgis.

    :param layer_name: name of the layer that generated the error
    :param exception: Exception instance
    """

    # log(f"An error occurred during layer add: {exception.__repr__()}")
    level = Qgis.MessageLevel.Critical

    # evaluate message depending on exception type
    try:
        raise exception
    # layer is empty
    except EmptyLayerException:
        level = Qgis.MessageLevel.Warning
        message = f"La couche {layer_name} est vide et n'a pas été ajoutée"
    # min zoom not respected
    except MinZoomException:
        level = Qgis.MessageLevel.Warning
        message = f"Vous devez zoomer pour charger la couche '{layer_name}'"
    # network error message
    except RequestsException:
        message = f"Erreur lors du téléchargement de la couche '{layer_name}'"
    except NotImplementedError:
        message = f"La couche '{layer_name}' nécessite des fonctionalités non implémentées pour le moment"
    # generic error message
    except Exception:
        message = f"Erreur lors de l'ajout de la couche '{layer_name}'"

        log(
            f"An error occured during layer add:\n{str(traceback.format_exc())}",
            Qgis.MessageLevel.Critical,
        )

    self.popup(message, level)
