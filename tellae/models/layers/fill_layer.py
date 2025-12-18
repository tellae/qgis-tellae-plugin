from .kite_layer import QgsKiteLayer


from qgis.core import (
    Qgis,
    QgsSymbolLayer,
    QgsSimpleFillSymbolLayer,
    QgsSymbol,
    QgsProperty,
)
from PyQt5.QtGui import QColor
from qgis.PyQt.QtCore import Qt

from tellae.utils import log


class KiteFillLayer(QgsKiteLayer):
    """
    A class for displaying Polygon geometries with borderless filled polygons.
    """

    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Polygon]

    def create_symbol(self):
        symbol = super().create_symbol()

        symbol_layer = symbol.symbolLayer(0)
        assert isinstance(symbol_layer, QgsSimpleFillSymbolLayer)

        # KiteFillLayer polygons are drawn without border stroke
        symbol_layer.setStrokeStyle(Qt.PenStyle.NoPen)

        return symbol

    def set_symbol_color(self, symbol: QgsSymbol, value: QColor | QgsProperty, data_defined=False):
        if data_defined:
            # set the FillColor property of the symbol layer
            symbol_layer = symbol.symbolLayer(0)
            symbol_layer.setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, value)
        else:
            symbol.setColor(value)

    def set_symbol_size(self, symbol: QgsSymbol, value, data_defined=False):
        log("Trying to set size on KiteFillLayer")

    def set_symbol_size_unit(self, symbol: QgsSymbol, value: Qgis.RenderUnit):
        log("Trying to set size unit on KiteFillLayer")

