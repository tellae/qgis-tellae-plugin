from tellae.panels.base_panel import BasePanel
from tellae.panels.data_table import DataTable
from tellae.utils.contexts import LayerDownloadContext, LayerInitContext
from tellae.utils.utils import log
from tellae.models.layers import GtfsLayers
from tellae.services.network import get_gtfs_routes_and_stops, gtfs_date_to_datetime
from qgis.PyQt.QtCore import Qt
from qgis.core import Qgis

class NetworkPanel(BasePanel):

    def __init__(self, main_dialog):

        super().__init__(main_dialog)

        self.search_text = ""

        self.network_lists = {
            "database": [],
            "project": []
        }

        self.database_network_table = DataTable(self, self.dlg.network_database_table)
        self.project_network_table = DataTable(self, self.dlg.network_project_table)

    def setup(self):
        # set default tab to 0
        self.dlg.add_network_tab.setCurrentIndex(0)

        self._set_table_headers(self.database_network_table, "database")
        self._set_table_headers(self.project_network_table, "project")

        self.dlg.network_search_bar.textChanged.connect(self.update_database_network_list)

    def _set_table_headers(self, table, network_list: str):
        button_slot = table.table_button_slot(lambda x: self.add_network(network_list, x))
        table.set_headers([
            {"text": "Actions", "value": "actions", "width": 60, "slot": button_slot},
            {"text": "Nom", "value": "name", "width": 235},
            {
                "text": "AOM",
                "value": lambda x: x["moa"]["name"] if x["moa"] else x["moa_name"],
                "width": 150,
            },
            {"text": "Réseau", "value": "network_name", "width": 150},
            {
                "text": "Période",
                "value": lambda x: f'{gtfs_date_to_datetime(x["start_date"])} - {gtfs_date_to_datetime(x["end_date"])}' if x["start_date"] is not None else "",
                "width": 180,
                "align": Qt.AlignCenter,
            },
        ])

    def searched_gtfs(self):
        text = self.dlg.network_search_bar.text()
        if text == "":
            gtfs_list = self.store.database_gtfs_list
        else:
            text_lower = text.lower()
            gtfs_list = [
                x
                for x in self.store.database_gtfs_list
                if text_lower in x["name"].lower()
                or text_lower in x["network_name"].lower()
                or text_lower in (x["moa"]["name"] if x["moa"] else x["moa_name"]).lower()
            ]

        return gtfs_list

    # actions

    def add_network(self, network_list, row_idx):

        gtfs = self.network_lists[network_list][row_idx]

        if gtfs["status"] != "READY" or gtfs.get("_lastAnalysis", [{"status": "SUCCESS"}])[0]["status"] != "SUCCESS":
            self.store.main_dialog.display_message_bar("Le réseau est dans un état d'erreur et ne peut pas être ajouté", level=Qgis.MessageLevel.Warning)
            return

        name = gtfs["name"]

        def handler(geojson):
            with LayerInitContext(name):
                GtfsLayers(name=name, data=geojson).add_to_qgis()

        with LayerDownloadContext(name, handler) as ctx:
            get_gtfs_routes_and_stops(
                gtfs["uuid"], handler=ctx.handler, error_handler=ctx.error_handler
            )

    # database tab

    def update_database_network_list(self):

        self.network_lists["database"] = self.searched_gtfs()
        self.database_network_table.fill_table_with_items(self.network_lists["database"])

    def update_project_network_list(self):
        self.network_lists["project"] = self.store.project_gtfs_list
        self.project_network_table.fill_table_with_items(self.network_lists["project"])

    def on_project_update(self):
        self.update_project_network_list()