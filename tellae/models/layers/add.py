from . import *


def add_database_layer(layer_info):
    # preprocessing
    layer_data = {**layer_info, **layer_info.get("additionalProperties", dict())}
    layer_data["layer_id"] = layer_data["id"]

    # get layer class constructor
    layer_class = layer_data["layer_class"]
    if layer_class in LAYER_CLASSES:
        layer_constructor = LAYER_CLASSES[layer_class]
    else:
        raise ValueError(f"Unsupported layer class '{layer_class}'")

    # create layer instance
    layer = layer_constructor(**layer_data)

    # add layer to Qgis
    layer.add_to_qgis()


LAYER_CLASSES = {
    "KiteCircleLayer": KiteCircleLayer,
    "KiteLabelLayer": KiteLabelLayer,
    "KiteLineLayer": KiteLineLayer,
    "KiteFillLayer": KiteFillLayer,
    "StarlingLayer": StarlingLayer,
    "GeojsonLayer": GeojsonLayer,
}
