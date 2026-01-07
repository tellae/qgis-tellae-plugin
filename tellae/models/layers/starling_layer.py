from .line_layer import KiteLineLayer
from tellae.utils.constants import TELLAE_PRIMARY_COLOR, TELLAE_SECONDARY_COLOR
from qgis.core import (
    Qgis,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsFilledLineSymbolLayer,
    QgsGradientFillSymbolLayer,
    QgsSingleSymbolRenderer,
)
from PyQt5.QtGui import QColor
from qgis.PyQt.QtCore import Qt


class StarlingLayer(KiteLineLayer):

    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Line]

    def _update_style(self):
        fill_symbol_layer = QgsGradientFillSymbolLayer(QColor(TELLAE_PRIMARY_COLOR), QColor(TELLAE_SECONDARY_COLOR))

        fill_symbol = QgsFillSymbol([fill_symbol_layer])

        symbol_layer = QgsFilledLineSymbolLayer(width=3, fillSymbol=fill_symbol)
        symbol_layer.setPenCapStyle(Qt.PenCapStyle.RoundCap)

        symbol = QgsLineSymbol([symbol_layer])

        renderer = QgsSingleSymbolRenderer(symbol)

        self.qgis_layer.setRenderer(renderer)
