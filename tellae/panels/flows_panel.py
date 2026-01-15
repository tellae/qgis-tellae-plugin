from tellae.panels.base_panel import BasePanel
from tellae.panels.data_table import DataTable
from tellae.utils.utils import get_binary_name, log
from tellae.utils.constants import TELLAE_PRIMARY_COLOR
from tellae.utils.contexts import LayerDownloadContext
from tellae.models.layers import StarlingLayer, FlowmapFlowsLayer, FlowmapLocationsLayer
from tellae.services.project import get_project_binary_from_hash
from tellae.models.flowmap_data import FlowmapData


class FlowsPanel(BasePanel):

    def __init__(self, main_dialog):
        super().__init__(main_dialog)
        self.project_flows_table = DataTable(self, self.dlg.projectFlowsTable)

    def setup(self):
        button_slot = self.project_flows_table.table_button_slot(self.add_project_flows)
        self.project_flows_table.set_headers(
            [
                {
                    "text": "Nom",
                    "value": lambda x: get_binary_name(x, with_extension=False),
                    "width": 715,
                },
                {"text": "Actions", "value": "actions", "width": 60, "slot": button_slot},
            ]
        )

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
            # add Flowmap layers
            group = FlowmapFlowsLayer.create_legend_group(name)
            FlowmapFlowsLayer(
                data=aggregated_flowmap_data,
                name=name,
                group=group,
                editAttributes={"color": TELLAE_PRIMARY_COLOR}
            ).add_to_qgis()
            FlowmapLocationsLayer(
                data=aggregated_flowmap_data,
                name=name,
                group=group,
                editAttributes={"color": TELLAE_PRIMARY_COLOR}
            ).add_to_qgis()

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
                to_json=True,
            )

    # project tab

    def on_project_update(self):
        self.dlg.projectNameFlowsPanel.setText(f"Projet: {self.store.current_project_name}")
        self.project_flows_table.fill_table_with_items(self.store.get_project_data("flows"))
