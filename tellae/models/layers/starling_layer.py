from .line_layer import KiteLineLayer

from qgis.core import (
    Qgis,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsFilledLineSymbolLayer,
    QgsGradientFillSymbolLayer,
    QgsSingleSymbolRenderer
)
from PyQt5.QtGui import QColor
from qgis.PyQt.QtCore import Qt


class StarlingLayer(KiteLineLayer):

    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Line]

    def _update_style(self):
        fill_symbol_layer = QgsGradientFillSymbolLayer(QColor("#3d6482"), QColor("#85c287"))

        fill_symbol = QgsFillSymbol([fill_symbol_layer])

        symbol_layer = QgsFilledLineSymbolLayer(width=3, fillSymbol=fill_symbol)
        symbol_layer.setPenCapStyle(Qt.PenCapStyle.RoundCap)

        symbol = QgsLineSymbol([symbol_layer])

        renderer = QgsSingleSymbolRenderer(symbol)

        self.qgis_layer.setRenderer(renderer)
