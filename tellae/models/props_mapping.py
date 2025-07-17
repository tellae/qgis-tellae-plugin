from qgis.core import (
    Qgis,
    QgsSymbol,
    QgsProperty,
    QgsSingleSymbolRenderer,
    QgsCategorizedSymbolRenderer,
    QgsGraduatedSymbolRenderer,
    QgsRendererCategory,
    qgsfunction,
    QgsRendererRange,
    QgsClassificationCustom,
)
from PyQt5.QtGui import QColor

from abc import ABC, abstractmethod
import copy

from tellae.utils import log


MAPPING_CONSTS = {
    "population_densities_colors": [
        "#EFE3CF",
        "#F7C99E",
        "#F9AF79",
        "#F79465",
        "#E8705D",
        "#D4495A",
        "#D03568",
    ]
}

DEFAULT_LABEL_NAME = "Default"
DEFAULT_MAPPING_COLOR = "#bababa"
DEFAULT_MAPPING_SIZE = 1
DEFAULT_MAPPING_OPACITY = 1


class PaintTypeError(ValueError):
    def __init__(self):
        super().__init__("Paint type error")


@qgsfunction(group="Tellae", referenced_columns=[])
def prefixed_color(color):
    """
    Prepend # character to hex color if necessary
    """
    if color.startswith("#"):
        return color
    else:
        return "#" + color


@qgsfunction(group="Tellae", referenced_columns=[])
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

    def __init__(
        self,
        paint_type,
        mapping_options,
        paint=None,
        legend=False,
        legend_options=None,
        editable=True,
        **kwargs,
    ):

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

    def update_symbol(self, symbol: QgsSymbol, layer):
        """
        Update the given symbol according to the mapping context.

        The mapping context describes what part of the mapping data is used to evaluate
        the symbol paint. For instance, which interval of a graduated rendering, or which category
        of a categorized rendering.

        :param symbol: symbol to update
        :param layer: QgsKiteLayer instance being updated
        """

        paint_value, data_defined = self._to_paint_value()

        self._call_symbol_update(symbol, layer, paint_value, data_defined)

    def _call_symbol_update(self, symbol, layer, paint_value, data_defined):

        if self.paint_type == "opacity":
            layer.set_symbol_opacity(symbol, paint_value)
        elif self.paint_type == "color":
            layer.set_symbol_color(symbol, paint_value, data_defined=data_defined)
        elif self.paint_type == "size":
            layer.set_symbol_size(symbol, paint_value, data_defined=data_defined)
            layer.set_symbol_size_unit(symbol, self.SYMBOL_SIZE_UNIT)
        else:
            raise PaintTypeError

    @abstractmethod
    def _to_paint_value(self):
        """
        Transcribe the mapping into a paint value for QGIS symbology.

        There are two ways to set paint values:
        - Set a paint value calling the symbol's dedicated method (setColor, setStrokeWidth) with correct paint value
        - Call a 'setDataDefined*' method, allowing more complex values such as QGIS expressions

        This method returns a tuple, with the first item being the paint value
        and the second one is a boolean indicating if the paint is "data defined"

        :return: (paint_value, data_defined) tuple
        """

    def get_label(self, **kwargs) -> str:
        return ""

    def get_default_paint(self):
        if "default" in self.mapping_options:
            return self.mapping_options["default"]
        else:
            if self.paint_type == "color":
                return DEFAULT_MAPPING_COLOR
            elif self.paint_type == "size":
                return DEFAULT_MAPPING_SIZE
            elif self.paint_type == "opacity":
                return DEFAULT_MAPPING_OPACITY
            else:
                raise PaintTypeError

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
        symbol = layer.create_symbol()

        # update the symbol using the mapping
        self.update_symbol(symbol, layer)

        # update the symbol with secondary mappings
        symbol_updater(symbol)

        # create a QgsSingleSymbolRenderer from the symbol
        renderer = QgsSingleSymbolRenderer(symbol)

        return renderer

    # vector tiles styles

    def create_vector_tile_styles(self, layer):
        """
        Create a list of vector tiles styles from the mapping definition.

        The basic implementation of this method returns a single style containing
        a single symbol updated from the mapping paint definition.

        :param layer: QgsKiteLayer being styled

        :return: list of QgsVectorTileBasicRendererStyle instances
        """
        # create a single style
        style = layer.create_vector_tile_style(self.get_label())

        # update style from this props mapping
        self.update_symbol(style.symbol(), self)

        return [style]

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

    def _to_paint_value(self):
        """
        Fetch the paint constant value from the mapping options.
        """

        value = self.mapping_options["value"]

        if self.paint_type == "color":
            value = QColor(value)
        elif self.paint_type == "size":
            pass
        elif self.paint_type == "opacity":
            pass
        else:
            raise PaintTypeError

        return value, False

    def get_label(self, **kwargs):
        return self.mapping_options.get("label", None)


class DirectMapping(PropsMapping):
    mapping_type = "direct"

    def _to_paint_value(self):
        """
        Read the paint from a feature property.
        """
        key = self.mapping_options["key"]
        value_format = self.mapping_options.get("format", None)

        if self.paint_type == "color":
            if value_format == "raw":
                log("Format 'raw' is not implemented")
                expression = "0,0,0"
            elif value_format == "r g b":
                expression = f'r_g_b_color("{key}")'
            else:
                expression = f'prefixed_color("{key}")'
        elif self.paint_type == "size":
            expression = f'"{key}"'
        else:
            raise PaintTypeError

        return QgsProperty.fromExpression(expression), True


class CategoryMapping(PropsMapping):
    mapping_type = "category"

    def _to_paint_value(self):
        # implement this using CASE expression
        raise NotImplementedError

    def create_renderer(self, layer, symbol_updater) -> QgsCategorizedSymbolRenderer:
        """
        Create an instance of QgsCategorizedSymbolRenderer with the categories described by the mapping.

        :param layer:
        :param symbol_updater:
        :return:
        """

        categories = []
        for value in self.mapping_options["values_map"].keys():
            # create a symbol for each category
            symbol = layer.create_symbol()

            # update symbol with the category's associated paint value
            self.update_symbol_with_category_paint(symbol, layer, value)

            # update symbol with other mappings
            symbol_updater(symbol)

            # create the QgsRendererCategory instance
            category = QgsRendererCategory(value, symbol, self.get_label(value))

            categories.append(category)

        # create a default category
        symbol = layer.create_symbol()

        # update symbol with the category's associated paint value
        self.update_symbol_with_category_paint(symbol, layer, None, default=True)

        # update symbol with other mappings
        symbol_updater(symbol)

        default_category = QgsRendererCategory()
        default_category.setSymbol(symbol)
        default_category.setLabel(DEFAULT_LABEL_NAME)

        # default_category = QgsRendererCategory(NULL, symbol, DEFAULT_LABEL_NAME)

        categories.append(default_category)

        # create the QgsCategorizedSymbolRenderer instance
        renderer = QgsCategorizedSymbolRenderer(self.mapping_options["key"], categories)

        return renderer

    def create_vector_tile_styles(self, layer):
        """
        Create styles matching the categories described by the mapping.

        :param layer: QgsKiteLayer being styled
        :return:
        """
        key = self.mapping_options["key"]

        styles = []
        for value in self.mapping_options["values_map"].keys():
            # create a style for the features of the category
            style = layer.create_vector_tile_style(self.get_label(value))
            style.setFilterExpression(f"\"{key}\" IS '{value}'")

            # update paint
            self.update_symbol_with_category_paint(style.symbol(), layer, value)

            styles.append(style)

        # create a default style
        default_style = layer.create_vector_tile_style(DEFAULT_LABEL_NAME)
        default_style.setFilterExpression("ELSE")

        # update paint
        self.update_symbol_with_category_paint(default_style.symbol(), layer, None, default=True)

        styles.append(default_style)

        return styles

    def update_symbol_with_category_paint(self, symbol, layer, value, default=False):
        if default:
            paint_value = self.get_default_paint()
        else:
            paint_value = self.mapping_options["values_map"][value]

        if self.paint_type == "color":
            paint_value = QColor(paint_value)
        elif self.paint_type == "size":
            paint_value = paint_value
        else:
            raise PaintTypeError

        self._call_symbol_update(symbol, layer, paint_value, False)

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

    def _to_paint_value(self):
        # implement using CASE expression
        raise NotImplementedError

    def _evaluate_paint_value(self, **kwargs):
        interval = kwargs["interval"]
        if self.paint_type == "color":
            value = QColor(self.mapping_options["values"][interval])
        elif self.paint_type == "size":
            value = self.mapping_options["values"][interval]
        else:
            raise PaintTypeError

        return value, False

    def create_renderer(self, layer, symbol_updater) -> QgsGraduatedSymbolRenderer:
        """
        Create an instance of QgsGraduatedSymbolRenderer with the intervals described by the mapping.

        :param layer:
        :param symbol_updater:
        :return:
        """

        intervals = self.mapping_options["intervals"]
        range_list = []

        for i in range(len(intervals) + 1):
            # create a symbol for each interval
            symbol = layer.create_symbol()

            # update from mappings
            self.update_symbol_with_interval_paint(symbol, layer, i)

            # update symbol with other mappings
            symbol_updater(symbol)

            # evaluate interval bounds
            range_min = -100000 if i == 0 else intervals[i - 1]
            range_max = 100000 if i == len(intervals) else intervals[i]

            # create QgsRendererRange instance
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

    def create_vector_tile_styles(self, layer):
        """
        Create styles matching the intervals described by the mapping.

        :param layer: QgsKiteLayer being styled
        :return:
        """
        key = self.mapping_options["key"]
        intervals = self.mapping_options["intervals"]

        styles = []

        for i in range(len(intervals) + 1):
            # create style
            style = layer.create_vector_tile_style(self.get_label(i))

            # evaluate expression defining the interval
            if i == 0:
                filter_expression = f'"{key}" < {intervals[0]}'
            elif i == len(intervals):
                filter_expression = f'"{key}" >= {intervals[-1]}'
            else:
                filter_expression = f' ({intervals[i-1]} <= "{key}") AND ("{key}" < {intervals[i]})'
            style.setFilterExpression(filter_expression)

            # update style paint
            self.update_symbol_with_interval_paint(style.symbol(), layer, i)

            styles.append(style)

        return styles

    def update_symbol_with_interval_paint(self, symbol, layer, interval):

        if self.paint_type == "color":
            paint_value = QColor(self.mapping_options["values"][interval])
        elif self.paint_type == "size":
            paint_value = self.mapping_options["values"][interval]
        else:
            raise PaintTypeError

        self._call_symbol_update(symbol, layer, paint_value, False)

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

    # def _update_symbol_color(self, symbol: QgsSymbol, **kwargs):
    #     self.signal_incompatible_paint("color")

    def _to_paint_value(self):
        key = self.mapping_options["key"]

        if self.paint_type == "size":
            # exponential scale to max value 50*sqrt(100*PROP_VALUE/3.14)
            expression = (
                f'scale_exponential(@zoom_level, 0, 20, 0,  50*sqrt((100*"{key}")/3.14), 2)'
            )
        else:
            raise self.signal_incompatible_paint(self.paint_type)

        return QgsProperty.fromExpression(expression), True


class LinearZoomInterpolationMapping(PropsMapping):
    mapping_type = "linear_zoom_interpolation"

    # def _update_symbol_color(self, symbol: QgsSymbol, **kwargs):
    #     self.signal_incompatible_paint("color")

    def _to_paint_value(self):
        interpolation_values = self.mapping_options["interpolation_values"]
        paint_values = self.mapping_options["paint_values"]

        if self.paint_type == "size":
            # manage values under of interpolation interval
            expression = (
                f"CASE WHEN @zoom_level < {interpolation_values[0]} THEN {paint_values[0]} "
            )

            for i in range(len(interpolation_values) - 1):
                # perform a linear interpolation when zoom level is in an interpolation interval
                expression += (
                    f"WHEN @zoom_level BETWEEN {interpolation_values[i]} AND {interpolation_values[i+1]} "
                    f"THEN scale_linear(@zoom_level, {interpolation_values[i]}, {interpolation_values[i+1]}, {paint_values[i]}, {paint_values[i+1]}) "
                )

            # manage values up of interpolation interval
            expression += (
                f"WHEN @zoom_level > {interpolation_values[-1]} THEN {paint_values[-1]} END"
            )
        else:
            raise self.signal_incompatible_paint(self.paint_type)

        return QgsProperty.fromExpression(expression), True


class EnumMapping(PropsMapping):
    mapping_type = "enum"

    def _to_paint_value(self):
        raise self.signal_incompatible_paint(self.paint_type)

    # def update_symbol_as_secondary(self, symbol: QgsSymbol):
    #     raise self.signal_incompatible_paint(self.paint_type)
    #


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
            "mapping_options": {"value": mapping_init},
            "paint_type": inferred_paint_type,
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
    EnumMapping.mapping_type: EnumMapping,
}
