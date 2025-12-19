from .kite_layer import QgsKiteLayer

from qgis.core import (
    Qgis,
    QgsSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsMarkerSymbol,
    QgsProperty,
)
from PyQt5.QtGui import QColor
from qgis.PyQt.QtCore import Qt


class KiteCircleLayer(QgsKiteLayer):
    """
    A class for displaying Point geometries as borderless circles.
    """

    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Point]

    def create_symbol(self):
        symbol = super().create_symbol()

        symbol_layer = symbol.symbolLayer(0)
        assert isinstance(symbol_layer, QgsSimpleMarkerSymbolLayer)

        # KiteCircleLayer circles are drawn without border stroke
        symbol_layer.setStrokeStyle(Qt.PenStyle.NoPen)

        return symbol

    def set_symbol_color(
        self, symbol: QgsMarkerSymbol, value: QColor | QgsProperty, data_defined=False
    ):
        if data_defined:
            # set the FillColor property of the symbol layer
            symbol_layer = symbol.symbolLayer(0)
            symbol_layer.setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, value)
        else:
            symbol.setColor(value)

    def set_symbol_size(
        self, symbol: QgsMarkerSymbol, value: int | float | QgsProperty, data_defined=False
    ):
        if data_defined:
            symbol.setDataDefinedSize(value)
        else:
            symbol.setSize(value)

    def set_symbol_size_unit(self, symbol: QgsMarkerSymbol, value: Qgis.RenderUnit):
        symbol.setSizeUnit(value)
