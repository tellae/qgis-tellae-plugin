from .circle_layer import KiteCircleLayer
from tellae.utils.constants import TELLAE_PRIMARY_COLOR
from qgis.core import (
    Qgis,
)


class GtfsStopsLayer(KiteCircleLayer):
    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Point]

    def __init__(self, *args, **kwargs):

        # set editAttributes manually
        kwargs["editAttributes"] = {"color": TELLAE_PRIMARY_COLOR, "size": 5, "opacity": 0.7}

        kwargs["dataProperties"] = {"stop_id": "ID", "stop_name": "Nom"}

        super().__init__(*args, **kwargs)
