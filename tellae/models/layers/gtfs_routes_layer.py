from .line_layer import KiteLineLayer
from qgis.core import Qgis, QgsFeatureRequest, QgsSymbol
from qgis.PyQt.QtCore import Qt


class GtfsRoutesLayer(KiteLineLayer):
    """
    A class for displaying flows data with a FlowMap like layer.
    """

    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Line]

    def __init__(self, *args, **kwargs):

        # set editAttributes manually
        kwargs["editAttributes"] = {
            "color": {
                "type": "direct",
                "paint_type": "color",
                "mapping_options": {"key": "route_color", "default": "#000000"},
            },
            "size": {
                "type": "category",
                "paint_type": "size",
                "mapping_options": {
                    "key": "route_type",
                    "values_map": {0: 2, 1: 2, 2: 2, 3: 1},
                    "default": 0.75,
                },
            },
        }

        kwargs["dataProperties"] = {
            "route_id": "ID",
            "route_short_name": "Nom court",
            "route_long_name": "Nom long",
            "route_color": "Couleur",
        }

        super().__init__(*args, **kwargs)

    def infer_main_props_mapping(self):
        return self.edit_attributes["color"]

    def _update_style(self):
        super()._update_style()

        renderer = self.qgis_layer.renderer()

        # enabled order by
        renderer.setOrderByEnabled(True)
        # add order by clause
        order_by_clause = QgsFeatureRequest.OrderByClause("route_sort_order", ascending=False)
        renderer.setOrderBy(QgsFeatureRequest.OrderBy([order_by_clause]))

        self.qgis_layer.setRenderer(renderer)

    def set_symbol_size(self, symbol: QgsSymbol, value, data_defined=False):
        super().set_symbol_size(symbol, value, data_defined=data_defined)
        symbol_layer = symbol.symbolLayer(0)
        symbol_layer.setPenCapStyle(Qt.PenCapStyle.RoundCap)
        symbol_layer.setPenJoinStyle(Qt.PenJoinStyle.RoundJoin)
