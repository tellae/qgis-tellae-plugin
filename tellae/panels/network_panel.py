from tellae.panels.base_panel import BasePanel
from tellae.panels.data_table import DataTable
from tellae.utils.utils import log
from tellae.models.layers.gtfs_layers import GtfsLayer
from tellae.services.layers import LayerDownloadContext
from tellae.services.network import get_gtfs_routes_and_stops
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
            {"text": "Nom", "value": lambda x: self.gtfs_name(x), "width": 435},
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

    def gtfs_name(self, gtfs):
        return f'{gtfs["pt_network"]["moa"]["name"]} ({gtfs["pt_network"]["name"]})'

    # actions

    def add_network(self, row_idx):

        gtfs = self.network_list[row_idx]
        name = self.gtfs_name(gtfs)

        def handler(geojson):
            GtfsLayer(data=geojson, name=name).add_to_qgis()

        with LayerDownloadContext(name, handler) as ctx:
            get_gtfs_routes_and_stops(gtfs["uuid"], handler=ctx.handler, error_handler=ctx.error_handler)

    # database tab

    def update_network_list(self):
        self.network_list = self.store.gtfs_list
        self.database_network_table.fill_table_with_items(self.network_list)
