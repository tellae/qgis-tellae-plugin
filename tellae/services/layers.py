from tellae.utils.utils import (
    THEMES_TRANSLATION,
)
from tellae.utils.requests import request_whale
from tellae.tellae_store import TELLAE_STORE



def init_layers_table():
    def common_handler():
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

    def layer_summary_handler(response):
        result = response["content"]
        # filter visible layers
        layers = [layer for layer in result if layer["visible"]]

        # evaluate list of themes
        themes = list(set([theme for layer in layers for theme in layer["themes"]]))
        themes = [THEMES_TRANSLATION[theme] for theme in themes]

        # update store
        TELLAE_STORE.layer_summary = layers
        TELLAE_STORE.themes = sorted(themes)

        if TELLAE_STORE.layer_summary and TELLAE_STORE.datasets_summary:
            common_handler()

    request_whale("/shark/layers/table", handler=layer_summary_handler)

    def datasets_summary_handler(response):
        result = response["content"]
        datasets = {dataset["id"]: dataset for dataset in result}

        TELLAE_STORE.datasets_summary = datasets

        if TELLAE_STORE.layer_summary and TELLAE_STORE.datasets_summary:
            common_handler()

    request_whale("/shark/datasets/summary", handler=datasets_summary_handler)
