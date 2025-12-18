from .kite_layer import QgsKiteLayer

from qgis.core import (
    Qgis,
    QgsSymbolLayer,
    QgsSimpleFillSymbolLayer,
    QgsSymbol,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsProperty,
)
from PyQt5.QtGui import QColor
from qgis.PyQt.QtCore import Qt


class KiteLineLayer(QgsKiteLayer):
    """
    A class for displaying LineString and Polygon geometries with solid lines.
    """

    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Line, Qgis.GeometryType.Polygon]

    def create_symbol(self):
        symbol = super().create_symbol()

        if isinstance(symbol, QgsFillSymbol):
            symbol_layer = symbol.symbolLayer(0)
            assert isinstance(symbol_layer, QgsSimpleFillSymbolLayer)
            # KiteLineLayer polygons are drawn without fill color
            # and with a solid border stroke (as if it was a LineString)
            symbol_layer.setBrushStyle(Qt.BrushStyle.NoBrush)
            symbol_layer.setStrokeStyle(Qt.PenStyle.SolidLine)

        return symbol

    def set_symbol_color(self, symbol: QgsSymbol, value: QColor | QgsProperty, data_defined=False):
        symbol_layer = symbol.symbolLayer(0)
        if data_defined:
            # set the StrokeColor property of the symbol layer
            symbol_layer.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, value)
        else:
            if isinstance(symbol, QgsFillSymbol):
                # use setStrokeColor virtual method of QgsSymbolLayer
                symbol_layer.setStrokeColor(value)
            else:
                symbol.setColor(value)

    def set_symbol_size(
        self, symbol: QgsSymbol, value: int | float | QgsProperty, data_defined=False
    ):
        if data_defined:
            if isinstance(symbol, QgsLineSymbol):
                symbol.setDataDefinedWidth(value)
            else:
                # set the StrokeWidth property of the symbol layer
                symbol_layer = symbol.symbolLayer(0)
                symbol_layer.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, value)
        else:
            if isinstance(symbol, QgsLineSymbol):
                symbol.setWidth(value)
            else:
                symbol_layer = symbol.symbolLayer(0)
                # should be QgsSimpleFillSymbolLayer instance
                assert isinstance(symbol_layer, QgsSimpleFillSymbolLayer)
                symbol_layer.setStrokeWidth(value)

    def set_symbol_size_unit(self, symbol: QgsMarkerSymbol, value: Qgis.RenderUnit):
        if isinstance(symbol, QgsLineSymbol):
            symbol.setWidthUnit(value)
        else:
            symbol_layer = symbol.symbolLayer(0)
            assert isinstance(symbol_layer, QgsSimpleFillSymbolLayer)
            symbol_layer.setStrokeWidthUnit(value)
