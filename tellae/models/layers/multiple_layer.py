from .kite_layer import QgsKiteLayer
from abc import ABC, abstractmethod
from copy import deepcopy
from qgis.core import (
    QgsProject,
    QgsVectorTileBasicRendererStyle,
)

class MultipleLayer(QgsKiteLayer, ABC):
    """
    Layer containing several sub-layers (QgsKiteLayer instances).

    Sub-layers are added to a QgsLayerTreeGroup with the layer name.
    """

    def __init__(self, layer_data):

        super().__init__(layer_data)

        self.group = None

        self.sub_layers = []

        for i, spec in enumerate(self.sub_layer_specs()):
            layer_class = spec["layer_class"]
            geometry = spec["geometry"]
            layer_data_copy = deepcopy(layer_data)
            layer_data_copy["id"] = f"{self.id}-{i}"
            layer_data_copy["parent"] = self

            layer_data_copy["layer_class"] = layer_class
            layer_data_copy["verbose"] = False
            layer_data_copy["source_geometry"] = geometry

            layer = layer_class(layer_data_copy)

            self.sub_layers.append(layer)

    @abstractmethod
    def sub_layer_specs(cls):
        raise NotImplementedError
    sub_layer_specs = classmethod(sub_layer_specs)

    def setup(self):
        super().setup()

        for layer in self.sub_layers:
            layer.source = self.source

    def on_source_prepared(self):
        # create a group for the sublayers
        root = QgsProject.instance().layerTreeRoot()
        self.group = root.insertGroup(0, self.name)

        for layer in self.sub_layers:
            layer.on_source_prepared()

        self._on_layer_added()

    # paint methods

    def create_symbol(self):
        raise RuntimeError("Style method called on parent layer")

    def create_vector_tile_style(self, label) -> QgsVectorTileBasicRendererStyle:
        raise NotImplementedError
