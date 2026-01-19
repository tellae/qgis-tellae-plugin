from tellae.panels.base_panel import BasePanel
from tellae.panels.data_table import DataTable
from tellae.utils.contexts import LayerDownloadContext, LayerInitContext
from tellae.utils.utils import log
from tellae.models.layers import GtfsLayers
from tellae.services.network import get_gtfs_routes_and_stops, gtfs_date_to_datetime
from qgis.PyQt.QtCore import Qt


class NetworkPanel(BasePanel):

    def __init__(self, main_dialog):

        super().__init__(main_dialog)

        self.search_text = ""

        self.network_list = []

        self.database_network_table = DataTable(self, self.dlg.network_database_table)

    def setup(self):
        button_slot = self.database_network_table.table_button_slot(self.add_network)
        self.database_network_table.set_headers(
            [
                {"text": "Nom", "value": "name", "width": 435},
                {
                    "text": "Date",
                    "value": lambda x: f'{gtfs_date_to_datetime(x["start_date"])} - {gtfs_date_to_datetime(x["end_date"])}',
                    "width": 280,
                    "align": Qt.AlignCenter,
                },
                {"text": "Actions", "value": "actions", "width": 60, "slot": button_slot},
            ]
        )

        self.dlg.network_search_bar.textChanged.connect(self.update_network_list)

    def searched_gtfs(self):
        text = self.dlg.network_search_bar.text()
        if text == "":
            gtfs_list = self.store.gtfs_list
        else:
            gtfs_list = [x for x in self.store.gtfs_list if text.lower() in x["name"].lower()]

        return gtfs_list

    # actions

    def add_network(self, row_idx):

        gtfs = self.network_list[row_idx]
        name = gtfs["name"]

        def handler(geojson):
            with LayerInitContext(name):
                GtfsLayers(name=name, data=geojson).add_to_qgis()

        with LayerDownloadContext(name, handler) as ctx:
            get_gtfs_routes_and_stops(
                gtfs["uuid"], handler=ctx.handler, error_handler=ctx.error_handler
            )

    # database tab

    def update_network_list(self):

        self.network_list = self.searched_gtfs()
        self.database_network_table.fill_table_with_items(self.network_list)
