from .kite_layer import QgsKiteLayer

from qgis.core import (
    Qgis,
    QgsSymbol,
)


class KiteLabelLayer(QgsKiteLayer):
    """
    A class for displaying Point geometries with text labels.
    """

    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Point]

    def infer_main_props_mapping(self):

        try:
            return self.edit_attributes["text"]
        except KeyError:
            raise ValueError("KiteSymbolLayer mapping should have 'text' paint type")

    def _call_style_update(self):
        # KiteLabelLayer are displayed using labels and not symbols
        self.style.update_layer_labelling(self.style.main_props_mapping.mapping_options["key"])
        self.style.remove_symbology()

    def set_symbol_opacity(self, symbol: QgsSymbol, value: float):
        pass
