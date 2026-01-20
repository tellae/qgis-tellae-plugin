from .multiple_layer import MultipleLayer
from .layer_group import LayerGroup
from .line_layer import KiteLineLayer
from .circle_layer import KiteCircleLayer
from tellae.utils.constants import TELLAE_PRIMARY_COLOR
from qgis.core import (
    Qgis,
    QgsSimpleFillSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsSymbol,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsProperty,
    QgsArrowSymbolLayer,
    QgsFeatureRequest,
)
from PyQt5.QtGui import QColor


class FlowmapLayers(LayerGroup):
    """
    Layer group containing a FlowmapFlowsLayer and a FlowmapLocationsLayer.
    """

    def __init__(self, name, *args, **kwargs):

        super().__init__(name=name, verbose=True)

        if not "editAttributes" in kwargs:
            kwargs["editAttributes"] = {"color": TELLAE_PRIMARY_COLOR}

        # create two sub layers
        self.append_layer(
            FlowmapFlowsLayer(
                *args,
                **kwargs,
            )
        )
        self.append_layer(FlowmapLocationsLayer(*args, **kwargs))


class FlowmapFlowsLayer(KiteLineLayer):
    """
    A class for displaying flows data with a FlowMap like layer.
    """

    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Line]

    LAYER_VARIABLES = {"min_flow_width": 0.5, "max_flow_width": 6}

    def __init__(self, *args, **kwargs):

        self.flowmap_data = kwargs["data"]

        # convert data to geojson format
        kwargs["data"] = self.flowmap_data.to_geojson(flows=True, locations=False)

        super().__init__(*args, **kwargs)

    def _update_style(self):
        super()._update_style()

        renderer = self.qgis_layer.renderer()

        # enabled order by
        renderer.setOrderByEnabled(True)
        # add order by clause
        order_by_clause = QgsFeatureRequest.OrderByClause("count", ascending=True)
        renderer.setOrderBy(QgsFeatureRequest.OrderBy([order_by_clause]))

        self.qgis_layer.setRenderer(renderer)

    def get_max(self):
        return self.flowmap_data.max_flow_magnitude

    def create_symbol(self):

        # create an arrow symbol layer
        arrow_symbol_layer = QgsArrowSymbolLayer()

        # set properties to make it look like FlowMap
        arrow_symbol_layer.setHeadType(QgsArrowSymbolLayer.HeadType.HeadSingle)  # single direction
        arrow_symbol_layer.setArrowType(QgsArrowSymbolLayer.ArrowType.ArrowRightHalf)  # half arrow

        # width defining expression
        expression = f'max(@min_flow_width, @max_flow_width/{self.get_max()}*"count")'

        # set arrow size values
        arrow_symbol_layer.setDataDefinedProperty(
            QgsArrowSymbolLayer.Property.ArrowWidth, QgsProperty.fromExpression(expression)
        )
        arrow_symbol_layer.setDataDefinedProperty(
            QgsArrowSymbolLayer.Property.ArrowStartWidth, QgsProperty.fromExpression(expression)
        )
        arrow_symbol_layer.setDataDefinedProperty(
            QgsArrowSymbolLayer.Property.ArrowHeadLength, QgsProperty.fromExpression(expression)
        )
        arrow_symbol_layer.setDataDefinedProperty(
            QgsArrowSymbolLayer.Property.ArrowHeadThickness, QgsProperty.fromExpression(expression)
        )
        arrow_symbol_layer.setOffset(0)

        # set arrow border color to white
        fill_symbol = arrow_symbol_layer.subSymbol()
        fill_symbol_layer = fill_symbol.symbolLayer(0)
        fill_symbol_layer.setStrokeColor(QColor("white"))
        fill_symbol_layer.setDataDefinedProperty(
            QgsSimpleFillSymbolLayer.Property.StrokeWidth,
            QgsProperty.fromExpression(f'0.2/{self.get_max()}*"count"'),
        )

        # create a QgisLineSymbol from the arrow symbol layer
        symbol = QgsLineSymbol([arrow_symbol_layer])

        return symbol

    def set_symbol_color(self, symbol: QgsSymbol, value: QColor | QgsProperty, data_defined=False):
        arrow_symbol_layer = symbol.symbolLayer(0)
        fill_symbol = arrow_symbol_layer.subSymbol()
        fill_symbol_layer = fill_symbol.symbolLayer(0)
        if data_defined:
            # set the FillColor property of the fill symbol layer
            fill_symbol_layer.setDataDefinedProperty(
                QgsSimpleFillSymbolLayer.Property.FillColor, value
            )
        else:
            if isinstance(fill_symbol, QgsFillSymbol):
                # use setColor virtual method of QgsSimpleFillSymbolLayer
                fill_symbol.setColor(value)

    def set_symbol_size(
        self, symbol: QgsSymbol, value: int | float | QgsProperty, data_defined=False
    ):
        raise NotImplementedError

    def set_symbol_size_unit(self, symbol, value: Qgis.RenderUnit):
        raise NotImplementedError


class FlowmapLocationsLayer(KiteCircleLayer):
    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Point]

    LAYER_VARIABLES = {"min_location_size": 1, "max_location_size": 6}

    def __init__(self, *args, **kwargs):
        self.flowmap_data = kwargs["data"]

        # convert data to geojson format
        kwargs["data"] = self.flowmap_data.to_geojson(flows=False, locations=True)

        super().__init__(*args, **kwargs)

    def get_max(self):
        return self.flowmap_data.max_internal_flow

    def create_symbol(self):

        symbol = super().create_symbol()

        symbol_layer = symbol.symbolLayer(0)

        # define size from expression
        expression = f'max(@min_location_size, @max_location_size/{self.get_max()}*"interne")'
        symbol_layer.setDataDefinedProperty(
            QgsSimpleMarkerSymbolLayer.Property.Size, QgsProperty.fromExpression(expression)
        )

        return symbol

    def set_symbol_size(
        self, symbol: QgsSymbol, value: int | float | QgsProperty, data_defined=False
    ):
        raise NotImplementedError

    def set_symbol_size_unit(self, symbol, value: Qgis.RenderUnit):
        raise NotImplementedError
