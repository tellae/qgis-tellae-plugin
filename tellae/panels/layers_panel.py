from tellae.panels.base_panel import BasePanel
from tellae.panels.data_table import DataTable
from tellae.utils.utils import get_binary_name, log
from tellae.models.layers.add import add_database_layer
from tellae.models.layers import GeojsonLayer
from tellae.services.project import get_project_binary_from_hash
from tellae.services.layers import LayerDownloadContext
from qgis.PyQt.QtCore import Qt


class LayersPanel(BasePanel):

    def __init__(self, main_dialog):

        super().__init__(main_dialog)

        self.selected_theme = "Tous"
        self.layers = []

        self.database_layers_table = DataTable(self, self.dlg.tableWidget)
        self.project_layers_table = DataTable(self, self.dlg.projectLayersTable)

    def setup(self):
        # set default tab to 0
        self.dlg.add_layers_tab.setCurrentIndex(0)

        # add listener on theme update
        self.dlg.themeSelector.currentTextChanged.connect(self.update_theme)

        # set database table headers
        button_slot = self.database_layers_table.table_button_slot(self.add_database_layer)
        self.database_layers_table.set_headers([
            {"text": "Nom", "value": lambda x: x["name"][self.store.locale], "width": 355},
            {
                "text": "Date",
                "value": lambda x: self.store.datasets_summary[x["main_dataset"]].get("date", ""),
                "width": 80,
                "align": Qt.AlignCenter,
            },
            {
                "text": "Source",
                "value": lambda x: self.store.datasets_summary[x["main_dataset"]]["provider_name"],
                "width": 280,
            },
            {"text": "Actions", "value": "actions", "width": 60, "slot": button_slot},
        ])

        # set project table headers
        button_slot = self.project_layers_table.table_button_slot(self.add_spatial_data)
        self.project_layers_table.set_headers([
            {
                "text": "Nom",
                "value": lambda x: get_binary_name(x, with_extension=False),
                "width": 729,
            },
            {"text": "Actions", "value": "actions", "width": 60, "slot": button_slot},
        ])

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
            GeojsonLayer(data=result["content"], name=name).add_to_qgis()

        with LayerDownloadContext(name, handler) as ctx:
            get_project_binary_from_hash(
                binary["hash"],
                "spatial_data",
                handler=ctx.handler,
                error_handler=ctx.error_handler,
                to_json=True,
            )

    def add_database_layer(self, index):

        layer_item = self.layers[index]
        add_database_layer(layer_item)

    # database tab

    def fill_theme_selector(self):
        # set list of layers
        self.dlg.themeSelector.addItems(["Tous"] + self.store.themes)

        # set default selection
        # to "all"
        self.dlg.themeSelector.setCurrentText("Tous")

    def fill_layers_table(self):
        # get list of layers to display
        self.layers = self.store.get_filtered_layer_summary(self.selected_theme)

        # fill table
        self.database_layers_table.fill_table_with_items(self.layers)

    # project tab

    def update_selected_project(self):
        self.dlg.projectNameLayersPanel.setText(f"Projet: {self.store.current_project_name}")
        self.project_layers_table.fill_table_with_items(self.store.get_project_data("spatial_data"))
