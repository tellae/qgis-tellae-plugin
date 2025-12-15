from tellae.panels.base_panel import BasePanel
from tellae.utils import *
from tellae.utils.utils import fill_table_widget, get_binary_name, log
from tellae.models.layers import add_flowmap_layer
from tellae.services.project import get_project_binary_from_hash
from tellae.services.layers import LayerDownloadContext
from qgis.PyQt.QtWidgets import QPushButton
from PyQt5.QtWidgets import QStyle
from qgis.PyQt.QtCore import Qt
from zipfile import ZipFile
import io
import csv
import json

class FlowsPanel(BasePanel):

    def setup(self):
        pass

    # actions

    def add_project_flows(self, row_idx):
        binary = self.store.get_project_data("flows")[row_idx]
        name = get_binary_name(binary, with_extension=False)

        def handler(result):
            geojson = self.flowmap_to_geojson(result["content"])
            add_flowmap_layer(geojson, name)

        with LayerDownloadContext(name, handler) as ctx:
            get_project_binary_from_hash(
                binary["hash"],
                "flows",
                handler=ctx.handler,
                error_handler=ctx.error_handler,
                to_json=False,
            )

    def agg_flows_records(self, flows_records):
        od_dict = dict()

        for flow in flows_records:
            origin = flow["origin"]
            dest = flow["dest"]
            pair = (origin, dest)
            count =  float(flow["count"])

            if pair not in od_dict:
                od_dict[pair] =count
            else:
                od_dict[pair] += count

        new_records = []
        for pair, count_sum in od_dict.items():
            new_records.append({
                "origin": pair[0],
                "dest": pair[1],
                "count": count_sum
            })

        return new_records

    def flowmap_to_geojson(self, stream):

        with ZipFile(io.BytesIO(stream)) as zipf:
            features = []

            locations_dict = dict()
            with zipf.open('locations.csv', mode="r") as locations_file:
                locations = self.csv_to_records(locations_file)

                for location in locations:
                    location_id = location["id"]
                    if location_id in locations_dict:
                        raise ValueError(f"Duplicated location id: '{location_id}'")
                    locations_dict[location_id] = [float(location["lon"]), float(location["lat"])]

                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [float(location["lon"]), float(location["lat"])]
                        },
                        "properties": {
                            "id": location_id,
                            "name": location.get("name", None)
                        }
                    }
                    features.append(feature)

            with zipf.open('flows.csv', mode="r") as flows_file:
                flows = self.csv_to_records(flows_file)

                flows = self.agg_flows_records(flows)

                for flow in flows:
                    origin = flow["origin"]
                    dest = flow["dest"]
                    properties = flow.copy()
                    del properties["origin"]
                    del properties["dest"]
                    properties["count"] = float(properties["count"])
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [locations_dict[origin], locations_dict[dest]]
                        },
                        "properties": properties
                    }
                    features.append(feature)


        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        return geojson

    def csv_to_records(self, file):
        lines = [line.decode("utf-8") for line in file.readlines()]
        my_reader = csv.reader(lines, delimiter=',')

        headers = []
        records = []
        for i, row in enumerate(my_reader):
            if i == 0:
                headers = row
                continue

            records.append({headers[i]: row[i] for i in range(len(row))})

        return records

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
