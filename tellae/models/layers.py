import tempfile
from abc import ABC, abstractmethod
import urllib.parse

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsVectorTileLayer,
    Qgis,
    QgsSymbolLayer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsVectorTileBasicRendererStyle,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsSymbol,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsProperty,
    QgsFields,
    QgsArrowSymbolLayer,
    QgsExpressionContextUtils,
    QgsFeatureRequest,
    QgsFilledLineSymbolLayer,
    QgsGradientFillSymbolLayer,
    QgsSingleSymbolRenderer
)
from PyQt5.QtGui import QColor
from qgis.PyQt.QtCore import Qt

from tellae.utils import log, MinZoomException, RequestsException
from tellae.tellae_store import TELLAE_STORE
from .layer_style import ClassicStyle, VectorTilesStyle
from .props_mapping import PropsMapping
from tellae.services.layers import LayerDownloadContext
from tellae.utils.requests import request, request_whale
import json
from copy import deepcopy


class LayerInitialisationError(Exception):
    pass


class QgsLayerSource(ABC):

    def __init__(self, layer):

        self.layer: QgsKiteLayer = layer

        self._is_prepared = False

    @property
    def layer_name(self) -> str:
        """
        Layer name, displayed in the QGIS user interface.
        """
        return self.layer.name

    @property
    def is_prepared(self):
        return self._is_prepared

    @abstractmethod
    def is_vector(self):
        raise NotImplementedError

    @abstractmethod
    def prepare(self):
        """
        Prepare the source for the creation of Qgis layers.
        """
        raise NotImplementedError

    def _mark_as_prepared(self):
        """
        Mark the source as prepared and signal the parent layer.
        """
        # mark source as prepared
        self._is_prepared = True

        # signal layer that source is ready and trigger following steps
        self.layer.on_source_prepared()

    def create_qgis_layer_instance(self, **kwargs):
        """
        Check that the source is prepared and create a QgsMapLayer instance.

        Actual implementation of the instance creation is in _create_qgis_layer_instance.

        :return: QgsMapLayer instance
        :raises: RuntimeError if this method is called on an unprepared source
        """
        if not self._is_prepared:
            raise RuntimeError("Calling method create_qgis_layer_instance on unprepared source")

        return self._create_qgis_layer_instance(**kwargs)

    @abstractmethod
    def _create_qgis_layer_instance(self, **kwargs):
        """
        Create a QgsMapLayer instance based on the source properties.

        :param kwargs: layer creation parameters
        :return: QgsMapLayer instance
        """
        raise NotImplementedError

    def error_handler(self, exception):
        """
        Handle errors encountered during the pipeline.

        :param exception: Exception subclass
        """
        TELLAE_STORE.main_dialog.signal_end_of_layer_add(self.layer_name, exception)


class GeojsonSource(QgsLayerSource):
    """
    A source that contains GeoJSON data stored in a temporary file.
    """

    def __init__(self, layer):
        super().__init__(layer)
        # geojson data bytes
        self.data: bytes | None = None

        # path to the temporary file containing the geojson source
        self.path = ""

    def is_vector(self):
        return False

    def prepare(self):
        if isinstance(self.layer.data, str):
            # if the data is an url, make a web request
            self.make_layer_request()
        elif isinstance(self.layer.data, dict):
            # if the data is a dict
            self.store_geojson_data(json.dumps(self.layer.data).encode("utf-8"))
        else:
            raise ValueError(f"Unsupported type for GeojsonSource data: {type(self.layer.data)}")

    def make_layer_request(self):
        with LayerDownloadContext(self.layer_name, self.on_request_success) as ctx:
            request(
                self.layer.data, handler=ctx.handler, error_handler=ctx.error_handler, to_json=False
            )

    def on_request_success(self, result):
        try:
            # store request response
            data = result["content"]
            if data is None:
                raise RequestsException("Empty response")

            self.store_geojson_data(data)

        except Exception as e:
            self.error_handler(e)

    def store_geojson_data(self, data: bytes):
        self.data = data

        self.create_temp_file()

        self._mark_as_prepared()

    def create_temp_file(self):
        try:
            file_path = self.path
            if file_path == "":
                file = tempfile.NamedTemporaryFile(suffix=".geojson")
                file.close()
                file_path = file.name
            with open(file_path, "wb") as f:
                f.write(self.data)
        except FileNotFoundError:
            raise FileNotFoundError
        except PermissionError:
            raise PermissionError

        self.path = file_path

    def _create_qgis_layer_instance(self, geometry=None, name=None):
        name = self.layer_name if name is None else name

        data = self.path
        if geometry is not None:
            data = f"{data}|geometrytype={geometry}"

        return QgsVectorLayer(data, name, "ogr")


class SharkSource(GeojsonSource):

    def get_url(self):
        return f"/shark/layers/geojson/{self.layer.data}"

    def prepare(self):
        with LayerDownloadContext(self.layer_name, self.on_request_success) as ctx:
            request_whale(
                self.get_url(), handler=ctx.handler, error_handler=ctx.error_handler, to_json=False
            )


class VectorTileGeojsonSource(SharkSource):

    def get_url(self) -> str:
        # evaluate bbox
        rect = TELLAE_STORE.tellae_services.iface.mapCanvas().extent()
        bbox = [rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum()]

        # reproject if necessary
        project = QgsProject.instance()
        current_crs = project.crs()
        if current_crs.authid() != "EPSG:4326":
            transform = QgsCoordinateTransform(
                current_crs, QgsCoordinateReferenceSystem("EPSG:4326"), project
            )

            minimum = transform.transform(rect.xMinimum(), rect.yMinimum())
            maximum = transform.transform(rect.xMaximum(), rect.yMaximum())

            bbox = [minimum.x(), minimum.y(), maximum.x(), maximum.y()]

        # url parameters
        params = {"bbox": f"{','.join([str(coord) for coord in bbox])}"}

        # evaluate selected properties

        # start with properties from dataProperties
        select = (
            list(self.layer.dataProperties.keys()) if self.layer.dataProperties is not None else []
        )

        # add edit attributes that read properties
        edit_attributes = self.layer.editAttributes
        if edit_attributes is None:
            edit_attributes = dict()

        for key in edit_attributes.keys():
            edit_attribute = edit_attributes[key]
            mapping_options = edit_attribute.mapping_options
            if "key" in mapping_options and not mapping_options["key"] in select:
                select.append(mapping_options["key"])

        if len(select) > 0:
            params["select"] = f"{','.join(select)}"

        # evaluate features filter
        if "filter" in self.layer.editAttributes:  # new way
            filter_mapping = self.layer.editAttributes["filter"]
            if filter_mapping.mapping_type != "enum":
                raise ValueError("Vector tiles filter is expected to be of type 'enum'")
            params["filter_key"] = filter_mapping.mapping_options["key"]
            params["filter_values"] = f"{','.join(filter_mapping.mapping_options['values'])}"
        elif "filter" in self.layer.mapboxProps:  # old way
            mapbox_filter = self.layer.mapboxProps["filter"]
            params["filter_key"] = mapbox_filter[1][1]
            params["filter_values"] = f"{','.join(mapbox_filter[2][1])}"

        return f"/shark/layers/geojson/{self.layer.data}?{urllib.parse.urlencode(params)}"


class VectorTileSource(QgsLayerSource):

    def __init__(self, layer):

        super().__init__(layer)

        self.uri = None

    def evaluate_uri(self):
        whale_endpoint = TELLAE_STORE.whale_endpoint
        auth_cfg = TELLAE_STORE.authCfg

        params = {"table": self.layer.data}

        # evaluate selected properties

        # start with properties from dataProperties
        select = (
            list(self.layer.dataProperties.keys()) if self.layer.dataProperties is not None else []
        )

        # add edit attributes that read properties
        edit_attributes = self.layer.editAttributes
        if edit_attributes is None:
            edit_attributes = dict()

        for key in edit_attributes.keys():
            edit_attribute = edit_attributes[key]
            mapping_options = edit_attribute.mapping_options
            if "key" in mapping_options and not mapping_options["key"] in select:
                select.append(mapping_options["key"])

        if len(select) > 0:
            params["select"] = f"[{','.join(select)}]"

        # evaluate features filter
        if "filter" in self.layer.editAttributes:  # new way
            filter_mapping = self.layer.editAttributes["filter"]
            if filter_mapping.mapping_type != "enum":
                raise ValueError("Vector tiles filter is expected to be of type 'enum'")
            params["filter_key"] = filter_mapping.mapping_options["key"]
            params["filter"] = f"[{','.join(filter_mapping.mapping_options['values'])}]"
        elif "filter" in self.layer.mapboxProps:  # old way
            mapbox_filter = self.layer.mapboxProps["filter"]
            params["filter_key"] = mapbox_filter[1][1]
            params["filter"] = f"[{','.join(mapbox_filter[2][1])}]"

        # build final url
        martin_url = (
            whale_endpoint
            + "/martin/table_selection/{z}/{x}/{y}".replace("{", "%7B").replace("}", "%7D")
            + f"?{urllib.parse.urlencode(params, safe='[]').replace('&', '%26')}"
        )

        # build final uri (with url type and auth config)
        uri = f"url={martin_url}&type=xyz&authcfg={auth_cfg}"

        return uri

    def is_vector(self):
        return True

    def prepare(self):
        # store url
        self.uri = self.evaluate_uri()

        # signal source as ready
        self._mark_as_prepared()

    def _create_qgis_layer_instance(self):
        return QgsVectorTileLayer(self.uri, self.layer_name)


class QgsKiteLayer:
    ACCEPTED_GEOMETRY_TYPES = []

    LAYER_VARIABLES = {}

    def __init__(self, layer_data, parent=None):

        self.parent_layer = parent

        self.id = layer_data["id"]

        self.layerClass = layer_data["layer_class"]

        self.data = layer_data.get("data", None)

        self.sourceType = layer_data.get("sourceType", "geojson")

        self.mapboxProps = layer_data.get("layerProps", dict())

        self.dataProperties = layer_data.get("dataProperties", dict())

        self.category = layer_data.get("category", None)

        self.verbose = layer_data.get("verbose", True)

        self.source_geometry = layer_data.get("source_geometry", None)

        if "name" in layer_data:
            name = layer_data["name"]
            if isinstance(name, dict):
                self.name = name[TELLAE_STORE.locale]
            else:
                self.name = name
        else:
            self.name = "Unnamed"

        self.datasets = layer_data.get("datasets", [])
        self.main_dataset = layer_data.get("main_dataset", None)

        # TODO: what data structure
        self.filter = layer_data.get("filter", None)

        self.editAttributes = layer_data.get("editAttributes", dict())
        self._read_edit_attributes()

        self.qgis_layer = None

        self.style = None

        self.source = None

    @property
    def is_vector(self):
        return self.source.is_vector()

    @property
    def geometry_type(self) -> Qgis.GeometryType | None:
        if self.qgis_layer is None:
            return None
        return self.qgis_layer.geometryType()

    def setup(self):
        self.source = self._init_source()

    def _init_source(self) -> QgsLayerSource:
        if self.sourceType == "geojson":
            return GeojsonSource(self)
        elif self.sourceType == "shark":
            return SharkSource(self)
        elif self.sourceType == "vector":
            if TELLAE_STORE.get_current_scale() > 2000000:
                raise MinZoomException
            return VectorTileGeojsonSource(self)
        else:
            raise ValueError(f"Unsupported source type '{self.sourceType}'")

    def on_source_prepared(self):
        """
        Create and set a QGIS layer instance from the source data, then call the pipeline to add it to QGIS.
        """

        # create a new QGIS layer instance
        self._create_qgis_layer()

        # bind variables to the layer
        self._create_layer_variables()

        # check layer instance
        self._validate_qgis_layer()

        # call the pipeline to add the layer to QGIS
        self._add_to_qgis()

    def _create_qgis_layer(self):
        self.qgis_layer = self.source.create_qgis_layer_instance(geometry=self.source_geometry)

    def _create_layer_variables(self):
        """
        Create a new variable in the layer's scope.
        """
        for key, value in self.LAYER_VARIABLES.items():
            QgsExpressionContextUtils.setLayerVariable(self.qgis_layer, key, value)

    def _validate_qgis_layer(self):
        if not self.qgis_layer.isValid():
            raise ValueError("QGIS layer is not valid")

        # check geometry type
        if self.geometry_type not in self.ACCEPTED_GEOMETRY_TYPES:
            raise ValueError(
                f"Unsupported geometry type '{self.geometry_type}' for layer class '{self.__class__.__name__}'"
            )

    def _create_style(self):
        if self.is_vector:
            style = VectorTilesStyle(self)
        else:
            style = ClassicStyle(self)
        self.style = style

    def _update_style(self):
        self._call_style_update()

    def _call_style_update(self):
        # update symbols if editAttributes are present
        if self.style.editAttributes:
            self.style.update_layer_symbology()

    def _update_aliases(self):
        for index in self.qgis_layer.attributeList():
            key = self.qgis_layer.attributeDisplayName(index)
            alias = None
            if key in self.dataProperties:
                if isinstance(self.dataProperties[key], dict):
                    alias = self.dataProperties[key][TELLAE_STORE.locale]
                elif isinstance(self.dataProperties[key], str):
                    alias = self.dataProperties[key]
                else:
                    raise ValueError(
                        f"Unsupported dataProperty type: {type(self.dataProperties[key])}"
                    )

            if alias is not None:
                self.qgis_layer.setFieldAlias(index, alias)

    def add_to_qgis(self):
        self.source.prepare()

    def _add_to_qgis(self):
        # add layer aliases
        self._update_aliases()

        # create a LayerStyle instance
        self._create_style()

        # update layer style
        self._update_style()

        # add layer to QGIS
        self._add_to_project()

        # callbacks on layer add
        self._on_layer_added()

    def _add_to_project(self):
        QgsProject.instance().layerTreeRegistryBridge().setLayerInsertionPoint(
            QgsProject.instance().layerTreeRoot(), 0
        )

        if self.qgis_layer.featureCount() == 0:
            return

        if self.parent_layer is not None and self.parent_layer.group is not None:
            # do not add the layer to the legend as it will already be added when linking group
            QgsProject.instance().addMapLayer(self.qgis_layer, False)
            self.parent_layer.group.addLayer(self.qgis_layer)
        else:
            QgsProject.instance().addMapLayer(self.qgis_layer)


    def _on_layer_added(self):
        # display a popup if verbose
        if self.verbose:
            TELLAE_STORE.main_dialog.signal_end_of_layer_add(self.name)

    def _read_edit_attributes(self):
        if self.editAttributes is not None:
            self.editAttributes = {
                key: PropsMapping.from_spec(key, spec) for key, spec in self.editAttributes.items()
            }

    def infer_main_props_mapping(self):

        legend = None
        non_constant = None
        color = None

        for key in self.editAttributes:
            mapping = self.editAttributes[key]
            if not mapping.paint:
                continue

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

    # paint methods

    def create_symbol(self):
        return QgsSymbol.defaultSymbol(self.geometry_type)

    def set_symbol_color(self, symbol: QgsSymbol, value, data_defined=False):
        pass

    def set_symbol_size(self, symbol: QgsSymbol, value, data_defined=False):
        pass

    def set_symbol_size_unit(self, symbol: QgsSymbol, value: Qgis.RenderUnit):
        pass

    def set_symbol_opacity(self, symbol: QgsSymbol, value: float):
        symbol.setOpacity(value)

    def create_vector_tile_style(self, label) -> QgsVectorTileBasicRendererStyle:
        # create a QgsVectorTileBasicRendererStyle instance
        style = QgsVectorTileBasicRendererStyle(label, None, self.geometry_type)

        # create and set the style's symbol
        symbol = self.create_symbol()
        style.setSymbol(symbol)

        return style



class MultipleLayer(QgsKiteLayer, ABC):
    """
    Layer containing several sub-layers (QgsKiteLayer instances).

    Sub-layers are added to a QgsLayerTreeGroup with the layer name.
    """

    def __init__(self, layer_data, parent=None):

        super().__init__(layer_data)

        sub_layers = []
        for i, spec in enumerate(self.sub_layer_specs()):
            layer_class = spec["layer_class"]
            geometry = spec["geometry"]
            layer_data_copy = deepcopy(layer_data)
            layer_data_copy["id"] = f"{self.id}-{i}"

            layer_data_copy["layer_class"] = layer_class
            layer_data_copy["verbose"] = False
            layer_data_copy["source_geometry"] = geometry
            layer = create_layer(layer_data_copy, parent=self)

            sub_layers.append(layer)

        self.sub_layers = sub_layers

        self.group = None

    @abstractmethod
    def sub_layer_specs(cls):
        raise NotImplementedError
    sub_layer_specs = classmethod(sub_layer_specs)

    def setup(self):
        super().setup()

        for layer in self.sub_layers:
            layer.source = self.source

    def on_source_prepared(self):
        # create a group for the sublayers
        root = QgsProject.instance().layerTreeRoot()
        self.group = root.insertGroup(0, self.name)

        for layer in self.sub_layers:
            layer.on_source_prepared()

        self._on_layer_added()

    # paint methods

    def create_symbol(self):
        raise RuntimeError("Style method called on parent layer")

    def create_vector_tile_style(self, label) -> QgsVectorTileBasicRendererStyle:
        raise NotImplementedError

class GeojsonLayer(MultipleLayer):

    def sub_layer_specs(cls):
        return [
            {"layer_class": "KiteCircleLayer", "geometry": "Point"},
            {"layer_class": "KiteLineLayer", "geometry": "LineString"},
            {"layer_class": "KiteFillLayer", "geometry": "Polygon"}
        ]
    sub_layer_specs = classmethod(sub_layer_specs)

class FlowmapLayer(MultipleLayer):

    def __init__(self, layer_data, parent=None):

        self.flowmap_data = layer_data["data"]

        layer_data["data"] = self.flowmap_data.to_geojson()

        super().__init__(layer_data, parent)

    def sub_layer_specs(cls):
        return [
            {"layer_class": "FlowmapFlowsLayer", "geometry": "LineString"},
            {"layer_class": "FlowmapLocationsLayer", "geometry": "Point"}
        ]
    sub_layer_specs = classmethod(sub_layer_specs)

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


class FlowmapFlowsLayer(KiteLineLayer):
    """
    A class for displaying flows data with a FlowMap like layer.
    """
    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Line]

    LAYER_VARIABLES = {
        "min_flow_width": 0.5,
        "max_flow_width": 6
    }

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
        return self.parent_layer.flowmap_data.max_flow_magnitude

    def create_symbol(self):

        # create an arrow symbol layer
        arrow_symbol_layer = QgsArrowSymbolLayer()

        # set properties to make it look like FlowMap
        arrow_symbol_layer.setHeadType(QgsArrowSymbolLayer.HeadType.HeadSingle)  # single direction
        arrow_symbol_layer.setArrowType(QgsArrowSymbolLayer.ArrowType.ArrowRightHalf)  # half arrow

        # width defining expression
        expression = f'max(@min_flow_width, @max_flow_width/{self.get_max()}*"count")'

        # set arrow size values
        arrow_symbol_layer.setDataDefinedProperty(QgsArrowSymbolLayer.Property.ArrowWidth, QgsProperty.fromExpression(expression))
        arrow_symbol_layer.setDataDefinedProperty(QgsArrowSymbolLayer.Property.ArrowStartWidth,
                                                  QgsProperty.fromExpression(expression))
        arrow_symbol_layer.setDataDefinedProperty(QgsArrowSymbolLayer.Property.ArrowHeadLength,
                                                  QgsProperty.fromExpression(expression))
        arrow_symbol_layer.setDataDefinedProperty(QgsArrowSymbolLayer.Property.ArrowHeadThickness,
                                                  QgsProperty.fromExpression(expression))
        arrow_symbol_layer.setOffset(0)

        # set arrow border color to white
        fill_symbol = arrow_symbol_layer.subSymbol()
        fill_symbol_layer = fill_symbol.symbolLayer(0)
        fill_symbol_layer.setStrokeColor(QColor("white"))
        fill_symbol_layer.setDataDefinedProperty(QgsSimpleFillSymbolLayer.Property.StrokeWidth, QgsProperty.fromExpression(f'0.2/{self.get_max()}*"count"'))

        # create a QgisLineSymbol from the arrow symbol layer
        symbol = QgsLineSymbol([arrow_symbol_layer])

        return symbol

    def set_symbol_color(self, symbol: QgsSymbol, value: QColor | QgsProperty, data_defined=False):
        arrow_symbol_layer = symbol.symbolLayer(0)
        fill_symbol = arrow_symbol_layer.subSymbol()
        fill_symbol_layer = fill_symbol.symbolLayer(0)
        if data_defined:
            # set the FillColor property of the fill symbol layer
            fill_symbol_layer.setDataDefinedProperty(QgsSimpleFillSymbolLayer.Property.FillColor, value)
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

    LAYER_VARIABLES = {
        "min_location_size": 1,
        "max_location_size": 6
    }

    def get_max(self):
        return self.parent_layer.flowmap_data.max_internal_flow

    def create_symbol(self):

        symbol = super().create_symbol()

        symbol_layer = symbol.symbolLayer(0)

        # define size from expression
        expression = f'max(@min_location_size, @max_location_size/{self.get_max()}*"interne")'
        symbol_layer.setDataDefinedProperty(QgsSimpleMarkerSymbolLayer.Property.Size,
                                                  QgsProperty.fromExpression(expression))

        return symbol

    def set_symbol_size(
        self, symbol: QgsSymbol, value: int | float | QgsProperty, data_defined=False
    ):
        raise NotImplementedError

    def set_symbol_size_unit(self, symbol, value: Qgis.RenderUnit):
        raise NotImplementedError

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

class KiteLabelLayer(QgsKiteLayer):
    """
    A class for displaying Point geometries with text labels.
    """

    ACCEPTED_GEOMETRY_TYPES = [Qgis.GeometryType.Point]

    def infer_main_props_mapping(self):

        try:
            return self.editAttributes["text"]
        except KeyError:
            raise ValueError("KiteSymbolLayer mapping should have 'text' paint type")

    def _call_style_update(self):
        # KiteLabelLayer are displayed using labels and not symbols
        self.style.update_layer_labelling(self.style.main_props_mapping.mapping_options["key"])
        self.style.remove_symbology()

    def set_symbol_opacity(self, symbol: QgsSymbol, value: float):
        pass


def add_database_layer(layer_info):
    layer_data = {**layer_info, **layer_info.get("additionalProperties", dict())}

    add_layer(layer_data)


def add_custom_layer(geojson, name):
    # create layer
    layer_data = {
        "id": f"customlayer:{TELLAE_STORE.nb_custom_layers}",
        "layer_class": "GeojsonLayer",
        "data": geojson,
        "name": name,
    }
    add_layer(layer_data)

    # increment custom layer count
    TELLAE_STORE.increment_nb_custom_layers()


def add_flowmap_layer(flowmap_data, name):

    aggregated_flowmap_data = flowmap_data.agg_by_od()

    layer_data = {
        "id": f"customlayer:{TELLAE_STORE.nb_custom_layers}",
        "layer_class": "FlowmapLayer",
        "data": aggregated_flowmap_data,
        "name": name,
        "editAttributes": {
            "color": "#3d6482"
        }
    }

    add_layer(layer_data)

    # increment custom layer count
    TELLAE_STORE.increment_nb_custom_layers()

def add_starling_layer(starling_data, name):
    # create layer
    layer_data = {
        "id": f"customlayer:{TELLAE_STORE.nb_custom_layers}",
        "layer_class": "StarlingLayer",
        "data": starling_data,
        "name": name,
    }

    add_layer(layer_data)

    # increment custom layer count
    TELLAE_STORE.increment_nb_custom_layers()


def add_layer(layer_data):
    # create the layer instance
    try:
        layer_instance = create_layer(layer_data)
    except Exception:
        error = LayerInitialisationError
        TELLAE_STORE.main_dialog.signal_end_of_layer_add(None, error)
        return

    # setup and add the layer to Qgis
    try:
        layer_instance.setup()
        layer_instance.add_to_qgis()
    except Exception as e:
        TELLAE_STORE.main_dialog.signal_end_of_layer_add(layer_instance.name, e)


def create_layer(layer_data, parent=None) -> QgsKiteLayer:
    # get layer constructor
    layer_class = layer_data["layer_class"]
    if layer_class in LAYER_CLASSES:
        layer_constructor = LAYER_CLASSES[layer_class]
    else:
        raise ValueError(f"Unsupported layer class '{layer_class}'")

    # create and initialise layer instance
    layer_instance = layer_constructor.__new__(layer_constructor)
    layer_instance.__init__(layer_data, parent=parent)

    return layer_instance


LAYER_CLASSES = {
    "KiteCircleLayer": KiteCircleLayer,
    "KiteLabelLayer": KiteLabelLayer,
    "KiteLineLayer": KiteLineLayer,
    "KiteFillLayer": KiteFillLayer,
    "FlowmapLayer": FlowmapLayer,
    "FlowmapFlowsLayer": FlowmapFlowsLayer,
    "FlowmapLocationsLayer": FlowmapLocationsLayer,
    "StarlingLayer": StarlingLayer,
    "GeojsonLayer": GeojsonLayer,
}
