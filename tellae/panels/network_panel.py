from tellae.panels.base_panel import BasePanel
from tellae.panels.data_table import DataTable
from tellae.utils.utils import get_binary_name, log
from tellae.services.project import get_project_binary_from_hash
from tellae.services.layers import LayerDownloadContext
from qgis.PyQt.QtCore import Qt
import datetime


class NetworkPanel(BasePanel):

    def __init__(self, main_dialog):

        super().__init__(main_dialog)

        self.network_list = []

        self.database_network_table = DataTable(self, self.dlg.network_database_table)

    def setup(self):
        button_slot = self.database_network_table.table_button_slot(self.add_network)
        self.database_network_table.set_headers([
            {"text": "Nom", "value": lambda x: f'{x["pt_network"]["moa"]["name"]} ({x["pt_network"]["name"]})', "width": 435},
            {
                "text": "Date",
                "value": lambda x: f'{self.gtfs_date_to_datetime(x["start_date"])} - {self.gtfs_date_to_datetime(x["end_date"])}',
                "width": 280,
                "align": Qt.AlignCenter
            },
            {"text": "Actions", "value": "actions", "width": 60, "slot": button_slot},
        ])

    def gtfs_date_to_datetime(self, gtfs_date):
        res = datetime.datetime.strptime(gtfs_date, "%Y-%M-%d")
        return res.strftime("%d/%M/%Y")


    # actions

    def add_network(self, row_idx):
        binary = self.store.get_project_data("spatial_data")[row_idx]
        name = get_binary_name(binary, with_extension=False)

        def handler(result):
            pass
            # add_custom_layer(result["content"], name)

        with LayerDownloadContext(name, handler) as ctx:
            get_project_binary_from_hash(
                binary["hash"],
                "spatial_data",
                handler=ctx.handler,
                error_handler=ctx.error_handler,
                to_json=True,
            )

    # database tab

    def update_network_list(self):
        self.network_list = self.store.gtfs_list
        self.database_network_table.fill_table_with_items(self.network_list)
