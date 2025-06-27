from qgis.core import (
    QgsVectorTileBasicRendererStyle,
    Qgis,
    QgsSymbol,
    QgsSymbolLayer,
    QgsProperty,
    QgsSingleSymbolRenderer,
    QgsCategorizedSymbolRenderer,
QgsGraduatedSymbolRenderer,
    QgsRendererCategory,
    qgsfunction,
    QgsMarkerSymbolLayer,
    QgsLineSymbolLayer,
    QgsFillSymbol,
QgsMarkerSymbol,
QgsLineSymbol,
QgsRendererRange,
QgsClassificationCustom
)
from PyQt5.QtGui import QColor

from abc import ABC, abstractmethod
import copy

from ..utils import log


MAPPING_CONSTS = {
  "population_densities_colors": ["#EFE3CF", "#F7C99E", "#F9AF79", "#F79465", "#E8705D", "#D4495A", "#D03568"]
}

DEFAULT_LABEL_NAME = "Default"

class PaintTypeError(ValueError):
    def __init__(self):
        super().__init__("Paint type error")


@qgsfunction(group='Tellae', referenced_columns=[])
def prefixed_color(color):
    """
    Prepend # character to hex color if necessary
    """
    if color.startswith('#'):
        return color
    else:
        return "#" + color


@qgsfunction(group='Tellae', referenced_columns=[])
def r_g_b_color(color):
    """
    Convert 'r g b' string to 'r,g,b'
    """
    color_array = color.split(" ")
    assert len(color_array) == 3, "String should with format 'r g b'"

    return ",".join(color_array)

class PropsMapping(ABC):

    mapping_type = None

    SYMBOL_SIZE_UNIT = Qgis.RenderUnit.Points

    def __init__(self, paint_type, mapping_options, paint=None, legend=False, legend_options=None, editable=True, **kwargs):

        self.paint_type = paint_type
        self.mapping_options = mapping_options if mapping_options is not None else dict()

        # define default value depending on paint type
        if paint is None:
            if paint_type in ["filter", "sort"]:
                paint = False
            else:
                paint = True

        self.paint = paint
        self.legend = legend
        self.legend_options = dict() if legend_options is None else legend_options
        self.editable = editable

    # updating symbols

    def update_symbol(self, symbol: QgsSymbol, **kwargs) -> str:
        """
        Update the given symbol according to the mapping context.

        The mapping context describes what part of the mapping data is used to evaluate
        the symbol paint. For instance, which interval of a graduated rendering, or which category
        of a categorized rendering.

        :param symbol: symbol to update
        :param kwargs: additional parameters that define the mapping context

        :return: eventual label associated to the context
        """

        if self.paint_type == "opacity":
            self._update_symbol_opacity(symbol, **kwargs)
        elif self.paint_type == "color":
            self._update_symbol_color(symbol, **kwargs)
        elif self.paint_type == "size":
            self._update_symbol_size(symbol, **kwargs)
            self._update_symbol_size_unit(symbol)
        else:
            raise PaintTypeError

        return self.get_label(**kwargs)


    @abstractmethod
    def update_symbol_as_secondary(self, symbol: QgsSymbol):
        """
        Update the given symbol as a secondary mapping.

        This means that this mapping is not the style defining mapping,
        and thus its rendering behaviour is not expressed by creating a
        dedicated renderer (for vector layers) or styles (for vector styles).
        Its style must then be expressed by setting properties of the renderer's
        sub symbols.

        The properties can still be set with values that describe a complex behaviour,
        most often using QGIS expressions.

        :param symbol: QgsSymbol instance to update
        """

    def _update_symbol_color(self, symbol: QgsSymbol, **kwargs):
        # call symbol setColor method
        symbol.setColor(self._evaluate_paint_value(**kwargs))

    def _update_symbol_size(self, symbol: QgsSymbol, **kwargs):
        # call relevant size method
        if isinstance(symbol, QgsMarkerSymbol):
            symbol.setSize(self._evaluate_paint_value(**kwargs))
        elif isinstance(symbol, QgsLineSymbol):
            symbol.setWidth(self._evaluate_paint_value(**kwargs))
        elif isinstance(symbol, QgsFillSymbol):
            log("Trying to use size paint on polygon layer")
            pass
        else:
            raise ValueError(f"Unsupported symbol class '{symbol.__class__.__name__}'")

    def _update_symbol_size_unit(self, symbol: QgsSymbol):
        # call relevant size unit method
        if isinstance(symbol, QgsMarkerSymbol):
            symbol.setSizeUnit(self.SYMBOL_SIZE_UNIT)
        elif isinstance(symbol, QgsLineSymbol):
            symbol.setWidthUnit(self.SYMBOL_SIZE_UNIT)
        elif isinstance(symbol, QgsFillSymbol):
            log("Trying to set size unit on polygon layer")
            pass
        else:
            raise ValueError(f"Unsupported symbol class '{symbol.__class__.__name__}'")

    def _update_symbol_opacity(self, symbol: QgsSymbol, **kwargs):
        if self.mapping_type != "constant":
            raise ValueError("Opacity mapping should be of type 'constant'")

        # call symbol setOpacity method
        symbol.setOpacity(self.mapping_options["value"])


    @abstractmethod
    def _evaluate_paint_value(self, **kwargs):
        raise NotImplementedError

    def get_label(self, **kwargs) -> str:
        return ""

    # vector layer style

    def create_renderer(self, layer, symbol_updater: callable):
        """
        Create a renderer that reflects the style described by the mapping class.

        The returned object is an instance of a subclass of QgsFeatureRenderer,
        which is used for QGIS vector layers.

        This method can be overridden to return other rendering classes
        in case it is more relevant for the mapping.

        :param layer: QgsKiteLayer subclass instance
        :param symbol_updater: function that updates a symbol with secondary mappings
        :return: QgsFeatureRenderer subclass instance
        """
        # create a symbol matching the layer geometry
        symbol = create_default_symbol(layer.GEOMETRY_TYPE)

        # update the symbol using the mapping
        self.update_symbol(symbol)

        # update the symbol with secondary mappings
        symbol_updater(symbol)

        # create a QgsSingleSymbolRenderer from the symbol
        renderer = QgsSingleSymbolRenderer(symbol)

        return renderer

    # vector tiles styles

    def create_vector_tile_styles(self, geometry_type):
        # create a single style
        style = create_vector_tile_style(self.get_label(), geometry_type)

        # update style from this props mapping
        self.update_style_paint(style)

        return [style]

    def update_style_paint(self, style, **kwargs):
        self.update_symbol(style.symbol(), **kwargs)

    # utils

    def signal_incompatible_paint(self, paint_type):
        message = f"Cannot update paint '{paint_type}' using {self.__class__.__name__} class"
        log(message)
        return ValueError(message)

    def from_spec(key, spec):
        log(key)
        log(spec)

        # repair and add missing value in mapping init json
        spec = repair_mapping_init(key, spec)

        try:
            mapping_type = spec["type"]
        except KeyError:
            raise ValueError("Missing 'type' field in mapping init")

        try:
            mapping_class = MAPPING_CLASSES[mapping_type]

            mapping = mapping_class.__new__(mapping_class)
            mapping.__init__(**spec)

        except KeyError:
            raise ValueError(f"Unsupported mapping type '{mapping_type}'")

        return mapping

    from_spec = staticmethod(from_spec)


class ConstantMapping(PropsMapping):
    mapping_type = "constant"

    def update_symbol_as_secondary(self, symbol: QgsSymbol):
        self.update_symbol(symbol)

    def _evaluate_paint_value(self):
        """
        Fetch the paint constant value from the mapping options.
        """

        if self.paint_type == "color":
            return QColor(self.mapping_options["value"])
        elif self.paint_type == "size":
            return self.mapping_options["value"]
        else:
            raise PaintTypeError

    def get_label(self, **kwargs):
        return self.mapping_options.get("label", None)


class DirectMapping(PropsMapping):
    mapping_type = "direct"

    def update_symbol_as_secondary(self, symbol: QgsSymbol):
        self.update_symbol(symbol)

    def _update_symbol_color(self, symbol: QgsSymbol, **kwargs):
        set_symbol_data_defined_color(symbol, self._evaluate_paint_value())

    def _update_symbol_size(self, symbol: QgsSymbol, **kwargs):
        set_symbol_data_defined_size(symbol, self._evaluate_paint_value())

    def _evaluate_paint_value(self):
        """
        Read the paint from a feature property.
        """
        key = self.mapping_options["key"]
        value_format = self.mapping_options.get("format", None)

        if self.paint_type == "color":
            if value_format == "raw":
                log("Format 'raw' is not implemented")
                expression = '0,0,0'
            elif value_format == "r g b":
                expression = f'r_g_b_color("{key}")'
            else:
                expression =  f'prefixed_color("{key}")'
        elif self.paint_type == "size":
            expression =  f'"{key}"'
        else:
            raise PaintTypeError

        return QgsProperty.fromExpression(expression)


class CategoryMapping(PropsMapping):
    mapping_type = "category"

    def update_symbol_as_secondary(self, symbol: QgsSymbol):
        # implement this using CASE expression
        raise NotImplementedError

    def _evaluate_paint_value(self, **kwargs):
        if "default" in kwargs and kwargs["default"]:
            paint_value = self.mapping_options["default"]
        else:
            paint_value = self.mapping_options["values_map"][kwargs["value"]]


        if self.paint_type == "color":
            return QColor(paint_value)
        elif self.paint_type == "size":
            return paint_value
        else:
            raise PaintTypeError

    def create_renderer(self, layer, symbol_updater) -> QgsCategorizedSymbolRenderer:
        """
        Create an instance of QgsCategorizedSymbolRenderer with the categories described by the mapping.

        :param layer:
        :param symbol_updater:
        :return:
        """

        categories = []
        for value, color in self.mapping_options["values_map"].items():
            symbol = create_default_symbol(layer.GEOMETRY_TYPE)
            label = self.update_symbol(symbol, value=value)
            symbol_updater(symbol)

            category = QgsRendererCategory(value, symbol, label)

            categories.append(category)

        renderer = QgsCategorizedSymbolRenderer(self.mapping_options["key"], categories)

        return renderer

    def create_vector_tile_styles(self, geometry_type):
        """
        Create styles matching the categories described by the mapping.

        :param geometry_type:
        :return:
        """
        key = self.mapping_options["key"]

        styles = []
        for value in self.mapping_options["values_map"].keys():
            # create a style for the features of the category
            style = create_vector_tile_style(self.get_label(value), geometry_type)
            style.setFilterExpression(f"\"{key}\" IS '{value}'")

            # update paint
            self.update_style_paint(style, value=value)

            styles.append(style)

        if "default" in self.mapping_options:
            default_style = create_vector_tile_style(DEFAULT_LABEL_NAME, geometry_type)
            default_style.setFilterExpression("ELSE")

            # update paint
            self.update_style_paint(default_style, default=True)

            styles.append(default_style)

        return styles

    def get_label(self, value):
        if "values_labels" in self.mapping_options:
            label = self.mapping_options["values_labels"][value]
        else:
            label = value

        return label


class ContinuousMapping(PropsMapping):
    mapping_type = "continuous"

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        if isinstance(self.mapping_options["values"], str):
            self.mapping_options["values"] = MAPPING_CONSTS[self.mapping_options["values"]]

    def update_symbol_as_secondary(self, symbol: QgsSymbol):
        # implement using CASE expression
        raise NotImplementedError

    def _evaluate_paint_value(self, **kwargs):
        interval = kwargs["interval"]
        if self.paint_type == "color":
            return QColor(self.mapping_options["values"][interval])
        elif self.paint_type == "size":
            return self.mapping_options["values"][interval]
        else:
            raise PaintTypeError

    def create_renderer(self, layer, symbol_updater) -> QgsGraduatedSymbolRenderer:
        """
        Create an instance of QgsGraduatedSymbolRenderer with the intervals described by the mapping.

        :param layer:
        :param symbol_updater:
        :return:
        """

        intervals = self.mapping_options["intervals"]
        range_list = []

        for i in range(len(intervals)+1):
            # create range symbol
            symbol = create_default_symbol(layer.GEOMETRY_TYPE)

            # update from mappings
            self.update_symbol(symbol, interval=i)

            symbol_updater(symbol)

            # evaluate range bounds
            range_min = -100000 if i == 0 else intervals[i-1]
            range_max = 100000 if i == len(intervals) else intervals[i]

            # create range instance
            renderer_range = QgsRendererRange(range_min, range_max, symbol, None)

            range_list.append(renderer_range)

        # create graduated renderer
        renderer = QgsGraduatedSymbolRenderer(self.mapping_options["key"], range_list)

        # set classification method and labels
        classification_method = QgsClassificationCustom()

        # label format and precision
        label_format = "%1 à %2"
        if "unit" in self.legend_options:
            label_format += f" {self.legend_options['unit']}"
        classification_method.setLabelFormat(label_format)
        classification_method.setLabelPrecision(0)
        renderer.setClassificationMethod(classification_method)
        renderer.updateRangeLabels()


        return renderer

    def create_vector_tile_styles(self, geometry_type):
        """
        Create styles matching the intervals described by the mapping.

        :param geometry_type:
        :return:
        """
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



class ExponentialZoomInterpolationMapping(PropsMapping):
    mapping_type = "exp_zoom_interpolation"

    def update_symbol_as_secondary(self, symbol: QgsSymbol):
        self.update_symbol(symbol)

    def _update_symbol_color(self, symbol: QgsSymbol, **kwargs):
        self.signal_incompatible_paint("color")

    def _update_symbol_size(self, symbol: QgsSymbol, **kwargs):
        set_symbol_data_defined_size(symbol, self._evaluate_paint_value())

    def _evaluate_paint_value(self):
        key = self.mapping_options["key"]

        if self.paint_type == "size":
            # exponential scale to max value 50*sqrt(100*PROP_VALUE/3.14)
            expression =  f'scale_exponential(@zoom_level, 0, 20, 0,  50*sqrt((100*"{key}")/3.14), 2)'
        else:
            raise self.signal_incompatible_paint(self.paint_type)

        return QgsProperty.fromExpression(expression)

class LinearZoomInterpolationMapping(PropsMapping):
    mapping_type = "linear_zoom_interpolation"

    def update_symbol_as_secondary(self, symbol: QgsSymbol):
        self.update_symbol(symbol)

    def _update_symbol_color(self, symbol: QgsSymbol, **kwargs):
        self.signal_incompatible_paint("color")

    def _update_symbol_size(self, symbol: QgsSymbol, **kwargs):
        set_symbol_data_defined_size(symbol, self._evaluate_paint_value())

    def _evaluate_paint_value(self):
        interpolation_values = self.mapping_options["interpolation_values"]
        paint_values = self.mapping_options["paint_values"]

        if self.paint_type == "size":
            # manage values under of interpolation interval
            expression = f"CASE WHEN @zoom_level < {interpolation_values[0]} THEN {paint_values[0]} "

            for i in range(len(interpolation_values)-1):
                # perform a linear interpolation when zoom level is in an interpolation interval
                expression += (f"WHEN @zoom_level BETWEEN {interpolation_values[i]} AND {interpolation_values[i+1]} "
                               f"THEN scale_linear(@zoom_level, {interpolation_values[i]}, {interpolation_values[i+1]}, {paint_values[i]}, {paint_values[i+1]}) ")

            # manage values up of interpolation interval
            expression += f"WHEN @zoom_level > {interpolation_values[-1]} THEN {paint_values[-1]} END"
        else:
            raise self.signal_incompatible_paint(self.paint_type)

        return QgsProperty.fromExpression(expression)


class EnumMapping(PropsMapping):
    mapping_type = "enum"

    def update_symbol_as_secondary(self, symbol: QgsSymbol):
        raise self.signal_incompatible_paint(self.paint_type)

    def _evaluate_paint_value(self, **kwargs):
        raise self.signal_incompatible_paint(self.paint_type)


def set_symbol_data_defined_size(symbol: QgsSymbol, qgs_property: QgsProperty):
    # call the relevant setDataDefined* method to set an expression defining the size
    if isinstance(symbol, QgsMarkerSymbol):
        symbol.setDataDefinedSize(qgs_property)
    elif isinstance(symbol, QgsLineSymbol):
        symbol.setDataDefinedWidth(qgs_property)
    elif isinstance(symbol, QgsFillSymbol):
        log("Trying to set size paint on polygon layer")
        pass
    else:
        raise ValueError(f"Unsupported symbol class '{symbol.__class__.__name__}'")

def set_symbol_data_defined_color(symbol: QgsSymbol, qgs_property: QgsProperty):
    # evaluate updated property based on symbol class
    if isinstance(symbol, QgsMarkerSymbol):
        updated_prop = QgsSymbolLayer.Property.FillColor  # QgsSymbolLayer.PropertyFillColor
    elif isinstance(symbol, QgsLineSymbol):
        updated_prop = QgsSymbolLayer.Property.StrokeColor  # QgsSymbolLayer.PropertyStrokeColor
    elif isinstance(symbol, QgsFillSymbol):
        updated_prop = QgsSymbolLayer.Property.FillColor  # QgsSymbolLayer.PropertyFillColor
    else:
        raise ValueError(f"Unsupported symbol class '{symbol.__class__.__name__}'")

    # the symbol is expected to have a single sub symbolLayer
    symbol_layer = symbol.symbolLayer(0)

    # use the setDataDefinedProperty method to set an expression defining the color
    symbol_layer.setDataDefinedProperty(
        updated_prop,
        qgs_property
    )

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

def repair_mapping_init(edit_key, mapping_init):

    # make a copy of the init json
    mapping_init = copy.deepcopy(mapping_init)

    # infer paint type from edit key
    if edit_key in ["color", "size", "opacity", "text", "filter", "sort"]:
        inferred_paint_type = edit_key
    else:
        inferred_paint_type = None

    # if edit attribute is a constant, create a 'constant' mapping init
    if isinstance(mapping_init, (str, float, int)):

        if inferred_paint_type is None:
            raise ValueError("Cannot infer paint type")

        mapping_init = {
            "type": "constant",
            "mapping_options": {
                "value": mapping_init
            },
            "paint_type": inferred_paint_type
        }

    # support deprecated 'mapping_data' field
    if "mapping_data" in mapping_init:
        mapping_init["mapping_options"] = mapping_init["mapping_data"]
        del mapping_init["mapping_data"]

    # support deprecated 'value_type' field
    if "value_type" in mapping_init:
        mapping_init["paint_type"] = mapping_init["value_type"]
        del mapping_init["value_type"]

    # add inferred paint type if missing
    if "paint_type" not in mapping_init:
        if inferred_paint_type is None:
            raise ValueError("Cannot infer paint type")
        else:
            mapping_init["paint_type"] = inferred_paint_type

    return mapping_init



MAPPING_CLASSES = {
    ConstantMapping.mapping_type: ConstantMapping,
    DirectMapping.mapping_type: DirectMapping,
    CategoryMapping.mapping_type: CategoryMapping,
    ContinuousMapping.mapping_type: ContinuousMapping,
    ExponentialZoomInterpolationMapping.mapping_type: ExponentialZoomInterpolationMapping,
    LinearZoomInterpolationMapping.mapping_type: LinearZoomInterpolationMapping,
    EnumMapping.mapping_type: EnumMapping
}


