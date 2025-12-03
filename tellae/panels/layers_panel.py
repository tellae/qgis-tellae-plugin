from tellae.panels.base_panel import BasePanel
from tellae.utils import *
from tellae.utils.utils import fill_table_widget, get_binary_name, log
from tellae.models.layers import create_layer, create_custom_layer
from tellae.services.project import get_project_binary_from_hash

from qgis.PyQt.QtWidgets import QPushButton
from PyQt5.QtWidgets import QStyle
from qgis.PyQt.QtCore import Qt


class LayersPanel(BasePanel):

    def __init__(self, main_dialog):

        super().__init__(main_dialog)

        self.selected_theme = "Tous"
        self.layers = []

    def setup(self):
        # add listener on theme update
        self.dlg.themeSelector.currentTextChanged.connect(self.update_theme)

    # actions

    def update_theme(self, new_theme):
        # update selected theme
        self.selected_theme = new_theme

        # update layers table
        self.fill_layers_table()

    def add_spatial_data(self, row_idx):
        binary = self.store.get_project_data("spatial_data")[row_idx]
        name = get_binary_name(binary, with_extension=False)

        def handler(result):
            try:
                qgs_kite_layer = create_custom_layer(result["content"], name)
                qgs_kite_layer.add_to_qgis()

            except Exception as e:
                log(e)
                # TELLAE_STORE.main_dialog.signal_end_of_layer_add(name, e)
                raise e

        get_project_binary_from_hash(binary["hash"], "spatial_data", handler, to_json=False)

    def add_layer(self, index):
        layer_item = self.layers[index]
        layer_name = layer_item.get("name", dict()).get(self.store.locale, "Unnamed")

        try:
            qgs_kite_layer = create_layer(layer_item)
            qgs_kite_layer.add_to_qgis()

        except Exception as e:
            self.dlg.signal_end_of_layer_add(layer_name, e)

    # database tab

    def fill_theme_selector(self):
        # set list of layers
        self.dlg.themeSelector.addItems(["Tous"] + self.store.themes)

        # set default selection
        # to "all"
        self.dlg.themeSelector.setCurrentText("Tous")

    def fill_layers_table(self):
        # get table widget
        table = self.dlg.tableWidget

        # get list of layers to display
        self.layers = self.store.get_filtered_layer_summary(self.selected_theme)

        # action slot

        def action_slot(table_widget, row_ix, col_ix, _, __):
            btn = QPushButton(table)
            btn.setIcon(self.dlg.style().standardIcon(QStyle.SP_DialogSaveButton))
            btn.clicked.connect(lambda state, x=row_ix: self.add_layer(x))
            table_widget.setCellWidget(row_ix, col_ix, btn)

        # setup table headers
        # total table length is 791, scroll bar is 16 => header width must total to 775
        headers = [
            {"text": "Nom", "value": lambda x: x["name"][self.store.locale], "width": 355},
            {
                "text": "Date",
                "value": lambda x: self.store.datasets_summary[x["main_dataset"]].get("date", ""),
                "width": 80,
                "align": Qt.AlignCenter,
            },
            {
                "text": "Source",
                "value": lambda x: self.store.datasets_summary[x["main_dataset"]][
                    "provider_name"
                ],
                "width": 280,
            },
            {"text": "Actions", "value": "actions", "width": 60, "slot": action_slot},
        ]

        fill_table_widget(table, headers, self.layers)

    # project tab

    def update_selected_project(self):
        self.dlg.projectNameLayersPanel.setText(f"Projet: {self.store.current_project_name}")
        self.fill_project_spatial_data_table()


    def fill_project_spatial_data_table(self):
        table = self.dlg.projectLayersTable

        spatial_data = self.store.get_project_data("spatial_data")

        def action_slot(table_widget, row_ix, col_ix, _, __):
            btn = QPushButton(table_widget)
            btn.setIcon(self.dlg.style().standardIcon(QStyle.SP_DialogSaveButton))
            btn.clicked.connect(lambda state, x=row_ix: self.add_spatial_data(x))
            table_widget.setCellWidget(row_ix, col_ix, btn)

        # setup table headers
        # total table length is 721, scroll bar is 16 => header width must total to 705
        headers = [
            {"text": "Nom", "value": lambda x: get_binary_name(x, with_extension=False), "width": 729},
            {"text": "Actions", "value": "actions", "width": 60, "slot": action_slot},
        ]

        fill_table_widget(table, headers, spatial_data)

    # utils



