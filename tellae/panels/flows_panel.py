from tellae.panels.base_panel import BasePanel
from tellae.utils import *
from tellae.utils.utils import fill_table_widget, get_binary_name, log
from tellae.models.layers import StarlingLayer, FlowmapLayer
from tellae.services.project import get_project_binary_from_hash
from tellae.services.layers import LayerDownloadContext
from qgis.PyQt.QtWidgets import QPushButton
from PyQt5.QtWidgets import QStyle
from tellae.models.flowmap_data import FlowmapData


class FlowsPanel(BasePanel):

    def setup(self):
        pass

    # actions

    def add_project_flows(self, row_idx):
        binary = self.store.get_project_data("flows")[row_idx]
        flow_type = binary["metadata"]["type"]
        if flow_type == "FLOWMAP":
            self.add_project_flowmap(binary)
        elif flow_type == "STARLING":
            self.add_project_starling_flows(binary)
        else:
            raise ValueError(f"Unsupported flows type '{flow_type}'")

    def add_project_flowmap(self, binary):
        name = get_binary_name(binary, with_extension=False)
        def handler(result):
            # read and aggregated flowmap data
            flowmap_data = FlowmapData.from_zip_stream(result["content"])
            aggregated_flowmap_data = flowmap_data.agg_by_od()
            # add flow as a StarlingLayer instance
            FlowmapLayer(data=aggregated_flowmap_data, name=name).add_to_qgis()

        with LayerDownloadContext(name, handler) as ctx:
            get_project_binary_from_hash(
                binary["hash"],
                "flows",
                handler=ctx.handler,
                error_handler=ctx.error_handler,
                to_json=False,
            )

    def add_project_starling_flows(self, binary):
        name = get_binary_name(binary, with_extension=False)
        def handler(result):
            # add flow as a StarlingLayer instance
            StarlingLayer(data=result["content"], name=name).add_to_qgis()

        with LayerDownloadContext(name, handler) as ctx:
            get_project_binary_from_hash(
                binary["hash"],
                "flows",
                handler=ctx.handler,
                error_handler=ctx.error_handler,
                to_json=True
            )

    # project tab

    def update_selected_project(self):
        self.dlg.projectNameFlowsPanel.setText(f"Projet: {self.store.current_project_name}")
        self.fill_project_spatial_data_table()

    def fill_project_spatial_data_table(self):
        table = self.dlg.projectFlowsTable

        spatial_data = self.store.get_project_data("flows")

        def action_slot(table_widget, row_ix, col_ix, _, __):
            btn = QPushButton(table_widget)
            btn.setIcon(self.dlg.style().standardIcon(QStyle.SP_DialogSaveButton))
            btn.clicked.connect(lambda state, x=row_ix: self.add_project_flows(x))
            table_widget.setCellWidget(row_ix, col_ix, btn)

        # setup table headers
        # total table length is 721, scroll bar is 16 => header width must total to 705
        headers = [
            {
                "text": "Nom",
                "value": lambda x: get_binary_name(x, with_extension=False),
                "width": 729,
            },
            {"text": "Actions", "value": "actions", "width": 60, "slot": action_slot},
        ]

        fill_table_widget(table, headers, spatial_data)

    # utils
