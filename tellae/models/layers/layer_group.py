from qgis.core import (
    Qgis,
    QgsProject,
)
from .layer_item import LayerItem


class LayerGroup(LayerItem):
    """
    Create a legend group to which layers can be appended.

    Layers are appended by providing this object as the 'group' parameter at layer creation.
    """

    def __init__(self, name=None, verbose=True):

        super().__init__(name=name, verbose=verbose)

        self._qgis_group = None

        self._layers = []

    @property
    def qgis_group(self):
        if self._qgis_group is None:
            self._qgis_group = self._create_qgis_group()
        return self._qgis_group

    @property
    def layers(self):
        return self._layers

    def _create_qgis_group(self):
        """
        Create a QgsLayerTreeGroup instance with the LayerGroup name at the project root.

        :return: new QgsLayerTreeGroup instance
        """
        root = QgsProject.instance().layerTreeRoot()
        return root.insertGroup(0, self.name)

    def append_layer(self, layer):
        """

        :param layer:
        :return:
        """
        # set group attribute of layer
        layer.set_group(self)

        # append layer to list
        self._layers.append(layer)

    def add_to_qgis(self):
        """
        Add all layers of the group to Qgis.
        """
        for layer in self._layers:
            layer.add_to_qgis()

        self.popup(
            f"Les couches '{self.name}' a été ajoutées avec succès !", Qgis.MessageLevel.Success
        )
