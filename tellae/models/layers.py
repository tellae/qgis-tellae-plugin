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
)
from PyQt5.QtGui import QColor
from qgis.PyQt.QtCore import Qt

from tellae.utils import log, MinZoomException, RequestsException
from tellae.tellae_store import TELLAE_STORE
from .layer_style import ClassicStyle, VectorTilesStyle
from .props_mapping import PropsMapping
import traceback
from tellae.utils.requests import request, request_whale


class QgsLayerSource(ABC):

    def __init__(self, layer):

        self.layer: QgsKiteLayer = layer

    @property
    def url(self) -> str:
        """
        Url requested by the source to get the layer contents.

        Ways of requesting the url may request from one source type to another.
        """
        raise NotImplementedError

    @property
    def layer_name(self) -> str:
        """
        Layer name, displayed in the QGIS user interface.
        """
        return self.layer.name

    @abstractmethod
    def _new_qgis_layer_instance(self):
        raise NotImplementedError

    @abstractmethod
    def init_qgis_layer(self):
        raise NotImplementedError

    @abstractmethod
    def is_vector(self):
        raise NotImplementedError

    def _set_qgis_layer(self):
        """
        Create and set a QGIS layer instance from the source data, then call the pipeline to add it.
        """

        # create a new QGIS layer instance
        qgis_layer = self._new_qgis_layer_instance()

        # set the QGIS layer instance in the QgsKiteLayer object
        self.layer._set_qgis_layer(qgis_layer)

        # call the pipeline to add the layer to QGIS
        self.layer._add_to_qgis()


class GeojsonSource(QgsLayerSource):

    def __init__(self, layer):
        super().__init__(layer)
        # store the request response
        self.response: bytes | None = None

        # store the layer data in a file (unused for now)
        self.path = ""

    @property
    def url(self):
        return self.layer.data

    def is_vector(self):
        return False

    def init_qgis_layer(self):
        # make a web request and read the geojson result as bytes
        if isinstance(self.layer.data, str):
            request(
                self.url, handler=self.on_download, error_handler=self.on_download_error, to_json=False
            )
        else:
            self.on_download({
                "content": self.layer.data
            })

    def on_download(self, response):
        try:
            # store request response
            self.response = response["content"]
            if self.response is None:
                raise RequestsException("Empty response")

            # call QGIS layer creation and add
            self._set_qgis_layer()

        except Exception as e:
            TELLAE_STORE.main_dialog.signal_end_of_layer_add(self.layer_name, e)

    def on_download_error(self, response):
        exception = response["exception"]
        TELLAE_STORE.main_dialog.signal_end_of_layer_add(self.layer_name, exception)

    def _new_qgis_layer_instance(self):
        try:
            file_path = self.path
            if file_path == "":
                file = tempfile.NamedTemporaryFile(suffix=".geojson")
                file.close()
                file_path = file.name
            with open(file_path, "wb") as f:
                f.write(self.response)
        except FileNotFoundError:
            raise FileNotFoundError
        except PermissionError:
            raise PermissionError

        return QgsVectorLayer(file_path, self.layer_name, "ogr")


class SharkSource(GeojsonSource):

    @property
    def url(self):
        return f"/shark/layers/geojson/{self.layer.data}"

    def init_qgis_layer(self):
        request_whale(
            self.url, handler=self.on_download, error_handler=self.on_download_error, to_json=False
        )


class VectorTileGeojsonSource(GeojsonSource):

    @property
    def url(self) -> str:
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

    def init_qgis_layer(self):
        request_whale(
            self.url, handler=self.on_download, error_handler=self.on_download_error, to_json=False
        )


class VectorTileSource(QgsLayerSource):

    @property
    def url(self):
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

    def init_qgis_layer(self):
        # nothing to download, just create the instance with the correct vector tiles url
        self._set_qgis_layer()

    def _new_qgis_layer_instance(self):
        return QgsVectorTileLayer(self.url, self.layer_name)


class QgsKiteLayer:
    ACCEPTED_GEOMETRY_TYPES = []

    def __init__(self, layer_data):
        self.id = layer_data["id"]

        self.layerClass = layer_data["layer_class"]

        self.data = layer_data.get("data", None)

        self.sourceType = layer_data.get("sourceType", "geojson")

        self.mapboxProps = layer_data.get("layerProps", dict())

        self.dataProperties = layer_data.get("dataProperties", dict())

        self.category = layer_data.get("category", None)

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

        self.source = self._init_source()

    @property
    def is_vector(self):
        return self.source.is_vector()

    @property
    def geometry_type(self) -> Qgis.GeometryType | None:
        if self.qgis_layer is None:
            return None
        return self.qgis_layer.geometryType()

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

    def _set_qgis_layer(self, qgis_layer):
        self.qgis_layer = qgis_layer

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
        TELLAE_STORE.main_dialog.start_layer_download(self.name)
        self.source.init_qgis_layer()

    def _add_to_qgis(self):
        # add layer aliases
        self._update_aliases()

        # create a LayerStyle instance
        self._create_style()

        # update layer style
        self._update_style()

        # add layer to QGIS
        self._add_to_project()

        # signal successful add
        TELLAE_STORE.main_dialog.signal_end_of_layer_add(self.name)

    def _add_to_project(self):
        QgsProject.instance().addMapLayer(self.qgis_layer)

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


def create_layer(layer_data):
    layer_data = {**layer_data, **layer_data.get("additionalProperties", dict())}

    layer_class = layer_data["layer_class"]

    if layer_class in LAYER_CLASSES:
        layer_constructor = LAYER_CLASSES[layer_class]
    else:
        raise ValueError(f"Unsupported layer class '{layer_class}'")

    layer_instance = layer_constructor.__new__(layer_constructor)
    layer_instance.__init__(layer_data)

    return layer_instance


def create_custom_layer(geojson, name):

    layer_data = {
        "id": f"customlayer:{TELLAE_STORE.nb_custom_layers}",
        "layer_class": "KiteLineLayer",
        "data": geojson,
        "name": name
    }
    TELLAE_STORE.increment_nb_custom_layers()

    layer_class = layer_data["layer_class"]

    if layer_class in LAYER_CLASSES:
        layer_constructor = LAYER_CLASSES[layer_class]
    else:
        raise ValueError(f"Unsupported layer class '{layer_class}'")

    layer_instance = layer_constructor.__new__(layer_constructor)
    layer_instance.__init__(layer_data)

    return layer_instance



LAYER_CLASSES = {
    "KiteCircleLayer": KiteCircleLayer,
    "KiteLabelLayer": KiteLabelLayer,
    "KiteLineLayer": KiteLineLayer,
    "KiteFillLayer": KiteFillLayer,
}
