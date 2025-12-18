from tellae.tellae_store import TELLAE_STORE
from . import *


def add_database_layer(layer_info):
    layer_data = {**layer_info, **layer_info.get("additionalProperties", dict())}

    add_layer(layer_data)


def add_custom_layer(geojson, name):
    # create layer
    layer_data = {
        "id": f"customlayer:{TELLAE_STORE.nb_custom_layers}",
        "layer_class": "GeojsonLayer",
        "data": geojson,
        "name": name,
    }
    add_layer(layer_data)

    # increment custom layer count
    TELLAE_STORE.increment_nb_custom_layers()


def add_flowmap_layer(flowmap_data, name):

    aggregated_flowmap_data = flowmap_data.agg_by_od()

    layer_data = {
        "id": f"customlayer:{TELLAE_STORE.nb_custom_layers}",
        "layer_class": "FlowmapLayer",
        "data": aggregated_flowmap_data,
        "name": name,
        "editAttributes": {
            "color": "#3d6482"
        }
    }

    add_layer(layer_data)

    # increment custom layer count
    TELLAE_STORE.increment_nb_custom_layers()

def add_starling_layer(starling_data, name):
    # create layer
    layer_data = {
        "id": f"customlayer:{TELLAE_STORE.nb_custom_layers}",
        "layer_class": "StarlingLayer",
        "data": starling_data,
        "name": name,
    }

    add_layer(layer_data)

    # increment custom layer count
    TELLAE_STORE.increment_nb_custom_layers()


def add_layer(layer_data):
    # create the layer instance
    try:
        layer_instance = create_layer(layer_data)
    except Exception:
        error = LayerInitialisationError
        TELLAE_STORE.main_dialog.signal_end_of_layer_add(None, error)
        return

    # setup and add the layer to Qgis
    try:
        layer_instance.setup()
        layer_instance.add_to_qgis()
    except Exception as e:
        TELLAE_STORE.main_dialog.signal_end_of_layer_add(layer_instance.name, e)

def create_layer(layer_data) -> QgsKiteLayer:
    # get layer constructor
    layer_class = layer_data["layer_class"]
    if layer_class in LAYER_CLASSES:
        layer_constructor = LAYER_CLASSES[layer_class]
    else:
        raise ValueError(f"Unsupported layer class '{layer_class}'")

    # create and initialise layer instance
    layer_instance = layer_constructor.__new__(layer_constructor)
    layer_instance.__init__(layer_data)

    return layer_instance



LAYER_CLASSES = {
    "KiteCircleLayer": KiteCircleLayer,
    "KiteLabelLayer": KiteLabelLayer,
    "KiteLineLayer": KiteLineLayer,
    "KiteFillLayer": KiteFillLayer,
    "FlowmapLayer": FlowmapLayer,
    "FlowmapFlowsLayer": FlowmapFlowsLayer,
    "FlowmapLocationsLayer": FlowmapLocationsLayer,
    "StarlingLayer": StarlingLayer,
    "GeojsonLayer": GeojsonLayer,
}

