from tellae.utils.utils import (
    THEMES_TRANSLATION,
    log,
)
from tellae.utils.requests import request_whale, RequestsException
from tellae.tellae_store import TELLAE_STORE



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

