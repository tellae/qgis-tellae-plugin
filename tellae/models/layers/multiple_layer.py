from .kite_layer import QgsKiteLayer
from abc import ABC, abstractmethod
from copy import deepcopy
from qgis.core import (
    QgsProject,
    QgsVectorTileBasicRendererStyle,
)


class MultipleLayer(QgsKiteLayer, ABC):
    """
    Layer containing several sub-layers sharing the same source.

    Sub-layers are added to a QgsLayerTreeGroup with the layer name.
    """

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.sub_layers = []

        for i, spec in enumerate(self.sub_layer_specs()):
            layer_class = spec["layer_class"]

            layer = layer_class(
                layer_id=f"{self.id}-{i}",
                data=self.data,
                editAttributes=kwargs.get("editAttributes", None),
                sourceType=self.source_type,
                dataProperties=self.data_properties,
                verbose=False,
                source_parameters={"geometry": spec["geometry"]},
                name=self.name,
                datasets=self.datasets,
                main_dataset=self.main_dataset,
                parent=self,
            )

            self.sub_layers.append(layer)

    @abstractmethod
    def sub_layer_specs(cls):
        raise NotImplementedError

    sub_layer_specs = classmethod(sub_layer_specs)

    def _setup(self):
        super()._setup()

        for layer in self.sub_layers:
            layer.source = self.source

    def on_source_prepared(self):
        # create a group for the sublayers
        self.group = self.create_legend_group(self.name)

        for layer in self.sub_layers:
            layer.group = self.group
            layer.on_source_prepared()

        self._on_layer_added()

    # paint methods

    def create_symbol(self):
        raise RuntimeError("Style method called on parent layer")

    def create_vector_tile_style(self, label) -> QgsVectorTileBasicRendererStyle:
        raise NotImplementedError
