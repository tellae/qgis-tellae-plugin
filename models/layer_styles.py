
from ..utils import log

from qgis.core import (
    QgsProject,
    QgsVectorTileBasicRendererStyle,
    Qgis,
    QgsSymbol,
    QgsFillSymbol,
    QgsSymbolLayer,
    QgsProperty,
    QgsSingleSymbolRenderer,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsVectorTileBasicLabeling,
    QgsVectorTileBasicLabelingStyle,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsLabelPlacementSettings,
    qgsfunction
)


from PyQt5.QtGui import QColor
from abc import ABC, abstractmethod

MAPPING_CONSTS = {
  "population_densities_colors": ["#EFE3CF", "#F7C99E", "#F9AF79", "#F79465", "#E8705D", "#D4495A", "#D03568"]
}


class LayerStyle:

    def __init__(self, layer):


        self.layer = layer

        self.originalRenderer = self.layer.qgis_layer.renderer()

        self.geometry_type = infer_geometry_type_from_layer_class(self.layer.layerClass)

        self.min_zoom_level = None
        if "minzoom" in self.layer.mapboxProps:
            self.min_zoom_level = self.layer.mapboxProps["minzoom"]

        self.editAttributes = self.layer.editAttributes

        self.main_props_mapping = None
        if self.layer.editAttributes:
            self.main_props_mapping = self.infer_main_props_mapping()


    @property
    def layer_renderer(self):
        return self.layer.qgis_layer.renderer()

    def infer_main_props_mapping(self):

        legend = None
        non_constant = None
        color = None

        for key in self.editAttributes:
            mapping = self.editAttributes[key]

            if mapping.legend:
                if legend is not None:
                    raise ValueError("Cannot have several 'legend' mappings")
                legend = mapping

            if mapping.mapping_type != "constant":
                if non_constant is not None:
                    raise ValueError("Cannot have several 'non-constant' mappings")
                non_constant = mapping

            if mapping.paint_type == "color":
                if color is not None:
                    raise ValueError("Cannot have several 'color' mappings")
                color = mapping

        if legend is not None:
            return legend

        if non_constant is not None:
            return non_constant

        if color is not None:
            return color

        raise ValueError("Could not infer main props mapping")

    def set_labelling(self, text_attribute):
        raise NotImplementedError


class VectorTilesStyle(LayerStyle):

    def update_layer(self):

        styles = self.create_styles()

        self.layer_renderer.setStyles(styles)


    def create_styles(self):

        secondary_mappings = [v for v in self.editAttributes.values() if v != self.main_props_mapping]

        styles = self.main_props_mapping.create_vector_tile_styles(self.geometry_type)

        for style in styles:
            for mapping in secondary_mappings:
                if mapping.mapping_type != "constant":
                    raise ValueError("Secondary mappings should have 'constant' type")

                mapping.update_style_paint(style)

        return styles

    def set_labelling(self, text_attribute):

        # add a buffer around text
        buffer_settings = QgsTextBufferSettings()
        # enable buffer
        buffer_settings.setEnabled(True)
        # fill buffer interior
        buffer_settings.setFillBufferInterior(True)
        # set fill color to white
        buffer_settings.setColor(QColor("white"))
        # set buffer settings into text format
        text_format = QgsTextFormat()
        text_format.setBuffer(buffer_settings)

        # placement settings
        placement_settings = QgsLabelPlacementSettings()
        # allow label overlap
        placement_settings.setOverlapHandling(Qgis.LabelOverlapHandling.AllowOverlapIfRequired)

        # create label settings and set values
        label_settings = QgsPalLayerSettings()
        label_settings.setFormat(text_format)
        label_settings.setPlacementSettings(placement_settings)

        # label value expression
        label_settings.fieldName = text_attribute

        # place labels over the point feature
        label_settings.placement = Qgis.LabelPlacement.OverPoint

        # enable labels
        label_settings.enabled = True

        # create labeling style from settings
        labeling_style = QgsVectorTileBasicLabelingStyle()
        labeling_style.setLabelSettings(label_settings)

        # set minimum zoom
        if self.min_zoom_level is not None:
            labeling_style.setMinZoomLevel(self.min_zoom_level)

        # create labeling for the layer with a single label style
        labeling = QgsVectorTileBasicLabeling()
        labeling.setStyles([labeling_style])
        self.layer.qgis_layer.setLabeling(labeling)


        # disable default rendering styles of the layer
        rendering_styles = self.layer_renderer.styles()
        for style in rendering_styles:
            log(style)
            style.setEnabled(False)

        self.layer_renderer.setStyles(rendering_styles)




class ClassicStyle(LayerStyle):

    def update_layer(self):



        renderer = self.main_props_mapping.create_renderer(self.layer, self.geometry_type)

        self.layer.qgis_layer.setRenderer(renderer)


class PropsMapping(ABC):

    mapping_type = None

    def __init__(self, paint_type, mapping_options, paint=True, legend=False, legend_options=None, editable=True, **kwargs):

        self.paint_type = paint_type
        self.mapping_options = mapping_options
        self.paint = paint
        self.legend = legend
        self.legend_options = dict() if legend_options is None else legend_options
        self.editable = editable

    def update_symbol(self, symbol: QgsSymbol, **kwargs):

        if self.paint_type == "opacity":
            symbol.setOpacity(self.mapping_options["value"])
        else:
            # we assume that we only manipulate symbols with a single symbol layer
            symbol_layer = symbol.symbolLayer(0)

            # evaluate the updated property based on the geometry type and paint type
            log(self.mapping_type)
            log(self.paint_type)
            updated_prop = infer_symbol_prop(infer_geometry_type_from_symbol_layer(symbol_layer), self.paint_type)

            # set the new property with a value depending on the props mapping
            symbol_layer.setDataDefinedProperty(
                updated_prop,
                QgsProperty.fromValue(self._evaluate_property_value(**kwargs))
            )

    def update_style_paint(self, style, **kwargs):
        self.update_symbol(style.symbol(), **kwargs)

    @abstractmethod
    def _evaluate_property_value(self, **kwargs):
        raise NotImplementedError

    def create_vector_tile_styles(self, geometry_type):
        # create a single style
        style = create_vector_tile_style(self.get_label(), geometry_type)

        # update style from this props mapping
        self.update_style_paint(style)

        return [style]

    def create_renderer(self, layer, geometry_type):
        return layer.renderer()


    @abstractmethod
    def get_label(self, **kwargs):
        raise NotImplementedError

    def from_spec(key, spec):
        log(key)
        log(spec)

        if key in ["color", "size", "opacity", "text", "filter"]:
            paint_type = key
        else:
            paint_type = None

        if isinstance(spec, (str, float, int)):

            if paint_type is None:
                raise ValueError("Cannot infer paint type")

            spec = {
                "type": "constant",
                "mapping_options": {
                    "value": spec
                },
                "paint_type": paint_type
            }

        if "mapping_data" in spec:
            spec["mapping_options"] = spec["mapping_data"]
            del spec["mapping_data"]

        if "value_type" in spec:
            spec["paint_type"] = spec["value_type"]
            del spec["value_type"]

        if "paint_type" not in spec:
            if paint_type is None:
                raise ValueError("Cannot infer paint type")
            else:
                spec["paint_type"] = paint_type

        mapping_type = spec["type"]
        del spec["type"]
        if mapping_type == "constant":
            mapping = ConstantMapping(**spec)
        elif mapping_type == "direct":
            mapping = DirectMapping(**spec)
        elif mapping_type == "category":
            mapping = CategoryMapping(**spec)
        elif mapping_type == "continuous":
            if isinstance(spec["mapping_options"]["values"], str):
                spec["mapping_options"]["values"] = MAPPING_CONSTS[spec["mapping_options"]["values"]]
            mapping = ContinuousMapping(**spec)
        else:
            raise ValueError(f"Unsupported mapping type '{mapping_type}'")

        return mapping

    from_spec = staticmethod(from_spec)


class ConstantMapping(PropsMapping):
    mapping_type = "constant"

    def _evaluate_property_value(self):

        if self.paint_type == "color":
            return QColor(self.mapping_options["value"])
        elif self.paint_type == "size":
            return self.mapping_options["value"]
        else:
            raise PaintTypeError

    def get_label(self, **kwargs):
        return self.mapping_options.get("label", None)

    def create_renderer(self, layer, geometry_type):

        symbol = create_default_symbol(geometry_type)

        self.update_symbol(symbol)

        renderer = QgsSingleSymbolRenderer(symbol)

        return renderer





class DirectMapping(PropsMapping):
    mapping_type = "direct"

    def _evaluate_property_value(self):
        key = self.mapping_options["key"]

        if self.paint_type == "color":
            expression =  f'prefixed_color("{key}")'
        elif self.paint_type == "size":
            expression =  f'"{key}"'
        else:
            raise PaintTypeError

        return QgsProperty.fromExpression(expression)

    def get_label(self, **kwargs):
        return None

    def create_renderer(self, layer, geometry_type):
        symbol = create_default_symbol(geometry_type)
        self.update_symbol(symbol)
        renderer = QgsSingleSymbolRenderer(symbol)



class CategoryMapping(PropsMapping):
    mapping_type = "category"

    def _evaluate_property_value(self, **kwargs):
        value = kwargs["value"]
        if self.paint_type == "color":
            return QColor(self.mapping_options["values_map"][value])
        elif self.paint_type == "size":
            return self.mapping_options["values_map"][value]
        else:
            raise PaintTypeError

    def create_renderer(self, layer, geometry_type):

        categories = []
        for value, color in self.mapping_options["values_map"].items():
            symbol = create_default_symbol(geometry_type)
            self.update_symbol(symbol, value=value)

            category = QgsRendererCategory(value, symbol, self.get_label(value))

            categories.append(category)

        renderer = QgsCategorizedSymbolRenderer(self.mapping_options["key"], categories)

        return renderer

    def create_vector_tile_styles(self, geometry_type):
        key = self.mapping_options["key"]

        styles = []
        for value in self.mapping_options["values_map"].keys():
            # create a style for the features of the category
            style = create_vector_tile_style(self.get_label(value), geometry_type)
            style.setFilterExpression(f"\"{key}\" IS '{value}'")

            # update paint
            self.update_style_paint(style, value=value)

            styles.append(style)

        return styles

    def get_label(self, value):
        if "values_labels" in self.mapping_options:
            label = self.mapping_options["values_labels"][value]
        else:
            label = value

        return label


class ContinuousMapping(PropsMapping):
    mapping_type = "continuous"

    def _evaluate_property_value(self, **kwargs):
        interval = kwargs["interval"]
        if self.paint_type == "color":
            return QColor(self.mapping_options["values"][interval])
        elif self.paint_type == "size":
            return self.mapping_options["values"][interval]
        else:
            raise PaintTypeError

    def create_renderer(self, layer, geometry_type):

        raise NotImplementedError

    def create_vector_tile_styles(self, geometry_type):
        key = self.mapping_options["key"]
        intervals = self.mapping_options["intervals"]

        styles = []

        style = create_vector_tile_style(self.get_label(0), geometry_type)
        style.setFilterExpression(f"\"{key}\" < {intervals[0]}")

        self.update_style_paint(style, interval=0)

        styles.append(style)

        for i in range(1, len(intervals)):
            style = create_vector_tile_style(self.get_label(i), geometry_type)
            style.setFilterExpression(f" ({intervals[i-1]} <= \"{key}\") AND (\"{key}\" < {intervals[i]})")
            # update paint
            self.update_style_paint(style, interval=i)

            styles.append(style)

        style = create_vector_tile_style(self.get_label(len(intervals)), geometry_type)
        style.setFilterExpression(f"\"{key}\" >= {intervals[-1]}")

        self.update_style_paint(style, interval=len(intervals))

        styles.append(style)

        return styles

    def get_label(self, interval):
        intervals = self.mapping_options["intervals"]
        if interval == 0:
            label = f"Moins de {intervals[0]}"
        elif interval == len(intervals):
            label = f"Plus de {intervals[-1]}"
        else:
            label = f"{intervals[interval-1]} à {intervals[interval]}"

        if "unit" in self.legend_options:
            label += f" {self.legend_options['unit']}"

        return label


def infer_symbol_prop(geometry_type: Qgis.GeometryType, paint_type: str):
    if geometry_type == Qgis.GeometryType.Line:
        if paint_type == "color":
            return QgsSymbolLayer.PropertyStrokeColor
        elif paint_type == "size":
            return QgsSymbolLayer.PropertyStrokeWidth
        else:
            raise PaintTypeError
    elif geometry_type == Qgis.GeometryType.Polygon:
        if paint_type == "color":
            return QgsSymbolLayer.PropertyFillColor
        elif paint_type == "size":
            log("Trying to use size paint on polygon layer")
            return None
        else:
            raise PaintTypeError
    elif geometry_type == Qgis.GeometryType.Point:
        if paint_type == "color":
            return QgsSymbolLayer.PropertyFillColor
        elif paint_type == "size":
            return QgsSymbolLayer.PropertySize
        else:
            raise PaintTypeError
    else:
        raise ValueError(f"Unsupported geometry type '{geometry_type}'")

def create_default_symbol(geometry_type):
    symbol = QgsSymbol.defaultSymbol(geometry_type)

    if geometry_type == Qgis.GeometryType.Polygon:
        symbol.symbolLayer(0).setStrokeStyle(0)
    elif geometry_type == Qgis.GeometryType.Point:
        symbol.symbolLayer(0).setStrokeStyle(0)

    return symbol


def create_vector_tile_style(label, geometry_type):
    style = QgsVectorTileBasicRendererStyle(label, None, geometry_type)

    symbol = create_default_symbol(geometry_type)
    style.setSymbol(symbol)

    return style


def infer_geometry_type_from_symbol_layer(symbol_layer):
    symbol_layer_class = symbol_layer.__class__.__name__

    if symbol_layer_class == "QgsSimpleFillSymbolLayer":
        return Qgis.GeometryType.Polygon
    elif symbol_layer_class == "QgsSimpleLineSymbolLayer":
        return Qgis.GeometryType.Line
    elif symbol_layer_class == "QgsSimpleMarkerSymbolLayer":
        return Qgis.GeometryType.Point
    else:
        raise ValueError(f"Unsupported symbol layer class '{symbol_layer_class}'")

def infer_geometry_type_from_layer_class(layer_class):
    if layer_class == "KiteCircleLayer":
        return Qgis.GeometryType.Point
    elif layer_class == "KiteSymbolLayer":
        return Qgis.GeometryType.Point
    elif layer_class == "KiteLineLayer":
        return Qgis.GeometryType.Line
    elif layer_class == "KiteFillLayer":
        return Qgis.GeometryType.Polygon
    else:
        raise ValueError(f"Unsupported layer class '{layer_class}'")

class PaintTypeError(ValueError):
    def __init__(self):
        super().__init__("Paint type error")


@qgsfunction(group='Custom', referenced_columns=[])
def prefixed_color(color):
    """

    """
    if color.startswith('#'):
        return color
    else:
        return "#" + color