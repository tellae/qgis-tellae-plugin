from zipfile import ZipFile
import io
import csv


class FlowmapData:
    """
    Wrapper class for Flowmap data.

    Flowmap data comes in this form:

    {
        "flows": [{"origin", "dest", "count", ...}, ..],
        "locations": [{"id", ?"name", "lon", "lat"}, ..]
    }
    """


    def __init__(self, flowmap_data):

        self.raw_data = flowmap_data

        self._flows = flowmap_data["flows"]
        self._locations = flowmap_data["locations"]

        self._locations_dict = self._evaluate_locations_dict()

        self._locations_stats = self._evaluate_locations_stats()

        self._max_flow_magnitude = self._evaluate_max_flow_magnitude()

        self._max_internal_flow = self._evaluate_max_internal_flow()

    @property
    def flows(self):
        return self._flows

    @property
    def locations(self):
        return self._locations

    @property
    def max_flow_magnitude(self):
        return self._max_flow_magnitude

    @property
    def max_internal_flow(self):
        return self._max_internal_flow

    def _evaluate_locations_dict(self):

        locations_dict = dict()

        for location in self.locations:
            location_id = location["id"]
            if location_id in locations_dict:
                raise ValueError(f"Duplicated Flowmap id: '{location_id}'")

            locations_dict[location_id] = location

        return locations_dict

    def _evaluate_locations_stats(self):
        # TODO: THIS IS ALREADY AGGREGATION
        location_stats = {location_id: {
                    "entrant": 0,
                    "sortant": 0,
                    "interne": 0
                } for location_id in self._locations_dict.keys()}

        for flow in self.flows:
            origin = flow["origin"]
            dest = flow["dest"]
            count = float(flow["count"])

            if origin == dest:
                location_stats[origin]["interne"] += count
            else:
                location_stats[origin]["sortant"] += count
                location_stats[dest]["entrant"] += count

        return location_stats

    def _evaluate_max_flow_magnitude(self):
        return max([float(flow["count"]) for flow in self.flows])

    def _evaluate_max_internal_flow(self):
        return max([stat["interne"] for stat in self._locations_stats.values()])

    def get_location_by_id(self, location_id):
        return self._locations_dict[location_id]

    def agg_by_od(self):
        od_dict = dict()

        for flow in self.flows:
            origin = flow["origin"]
            dest = flow["dest"]
            pair = (origin, dest)
            count =  float(flow["count"])

            if pair not in od_dict:
                od_dict[pair] =count
            else:
                od_dict[pair] += count

        new_flows = []
        for pair, count_sum in od_dict.items():
            new_flows.append({
                "origin": pair[0],
                "dest": pair[1],
                "count": count_sum
            })

        new_flowmap_data = {
            "flows": new_flows,
            "locations": self.locations
        }

        return FlowmapData(new_flowmap_data)

    def to_geojson(self, flows=True, locations=True):
        features = []

        if locations:
            for location in self.locations:
                properties = location.copy()
                del properties["lon"]
                del properties["lat"]
                properties.update(self._locations_stats[location["id"]])

                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(location["lon"]), float(location["lat"])]
                    },
                    "properties": properties
                }
                features.append(feature)

        if flows:
            for flow in self.flows:
                origin = self.get_location_by_id(flow["origin"])
                dest = self.get_location_by_id(flow["dest"])
                properties = flow.copy()
                del properties["origin"]
                del properties["dest"]
                properties["count"] = float(properties["count"])
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[float(origin["lon"]), float(origin["lat"])], [float(dest["lon"]), float(dest["lat"])]]
                    },
                    "properties": properties
                }
                features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features
        }

    def from_zip_stream(stream):
        flowmap_data = dict()
        with ZipFile(io.BytesIO(stream)) as zipf:

            with zipf.open('locations.csv', mode="r") as locations_file:
                flowmap_data["locations"] = csv_to_records(locations_file)

            with zipf.open('flows.csv', mode="r") as flows_file:
                flowmap_data["flows"] = csv_to_records(flows_file)

        return FlowmapData(flowmap_data)
    from_zip_stream = staticmethod(from_zip_stream)

# utils

def csv_to_records(file):
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