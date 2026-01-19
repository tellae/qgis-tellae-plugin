from .layer_group import LayerGroup
from .gtfs_stops_layer import GtfsStopsLayer
from .gtfs_routes_layer import GtfsRoutesLayer


class GtfsLayers(LayerGroup):
    """
    Layer group containing a GtfsStopsLayer and a GtfsRoutesLayer.
    """

    def __init__(self, name, *args, **kwargs):

        super().__init__(name=name, verbose=True)

        data = kwargs["data"]
        routes = data["routes"]
        stops = data["stops"]
        del kwargs["data"]

        # create two sub layers
        self.append_layer(GtfsStopsLayer(
            *args,
            **kwargs,
            data=stops
        ))
        self.append_layer(GtfsRoutesLayer(
            *args,
            **kwargs,
            data=routes
        ))
