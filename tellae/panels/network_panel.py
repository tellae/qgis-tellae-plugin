from tellae.panels.base_panel import BasePanel
from tellae.utils import *
from tellae.utils.utils import fill_table_widget, get_binary_name, log
from tellae.models.layers import add_custom_layer, add_database_layer
from tellae.services.project import get_project_binary_from_hash
from tellae.services.layers import LayerDownloadContext
from qgis.PyQt.QtWidgets import QPushButton
from PyQt5.QtWidgets import QStyle
from qgis.PyQt.QtCore import Qt


class NetworkPanel(BasePanel):

    def __init__(self, main_dialog):

        super().__init__(main_dialog)

        self.network_list = []

    def setup(self):
        pass

    # actions

    def add_network(self, row_idx):
        binary = self.store.get_project_data("spatial_data")[row_idx]
        name = get_binary_name(binary, with_extension=False)

        def handler(result):
            add_custom_layer(result["content"], name)

        with LayerDownloadContext(name, handler) as ctx:
            get_project_binary_from_hash(
                binary["hash"],
                "spatial_data",
                handler=ctx.handler,
                error_handler=ctx.error_handler,
                to_json=True,
            )

    # database tab

    def fill_network_table(self):
        pass
        # get table widget
        table = "TODO"

        # action slot

        def action_slot(table_widget, row_ix, col_ix, _, __):
            btn = QPushButton(table)
            btn.setIcon(self.dlg.style().standardIcon(QStyle.SP_DialogSaveButton))
            btn.clicked.connect(lambda state, x=row_ix: self.add_network(x))
            table_widget.setCellWidget(row_ix, col_ix, btn)

        # setup table headers
        # total table length is 791, scroll bar is 16 => header width must total to 775
        headers = [
            {"text": "Nom", "value": lambda x: f'{x["pt_network"]["moa"]["name"]} ({x["pt_network"]["name"]})', "width": 435},
            {
                "text": "Date",
                "value": lambda x: f'{x["start_date"]} - {x["end_date"]}',
                "width": 280,
            },
            {"text": "Actions", "value": "actions", "width": 60, "slot": action_slot},
        ]

        fill_table_widget(table, headers, self.store.gtfs_list)

    # utils
