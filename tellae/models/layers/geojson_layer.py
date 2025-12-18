from .multiple_layer import MultipleLayer
from .circle_layer import KiteCircleLayer
from .line_layer import KiteLineLayer
from .fill_layer import KiteFillLayer

class GeojsonLayer(MultipleLayer):

    def sub_layer_specs(cls):
        return [
            {"layer_class": KiteCircleLayer, "geometry": "Point"},
            {"layer_class": KiteLineLayer, "geometry": "LineString"},
            {"layer_class": KiteFillLayer, "geometry": "Polygon"}
        ]
    sub_layer_specs = classmethod(sub_layer_specs)