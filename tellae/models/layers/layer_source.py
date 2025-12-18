import tempfile
from abc import ABC, abstractmethod
import urllib.parse

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsVectorTileLayer,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,

)

from tellae.utils import log, RequestsException
from tellae.tellae_store import TELLAE_STORE
from tellae.services.layers import LayerDownloadContext
from tellae.utils.requests import request, request_whale
import json


class QgsLayerSource(ABC):

    def __init__(self, layer):

        self.layer = layer

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
            list(self.layer.data_properties.keys()) if self.layer.data_properties is not None else []
        )

        # add edit attributes that read properties
        edit_attributes = self.layer.edit_attributes
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
        if "filter" in self.layer.edit_attributes:  # new way
            filter_mapping = self.layer.edit_attributes["filter"]
            if filter_mapping.mapping_type != "enum":
                raise ValueError("Vector tiles filter is expected to be of type 'enum'")
            params["filter_key"] = filter_mapping.mapping_options["key"]
            params["filter_values"] = f"{','.join(filter_mapping.mapping_options['values'])}"
        elif "filter" in self.layer.mapbox_props:  # old way
            mapbox_filter = self.layer.mapbox_props["filter"]
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
            list(self.layer.data_properties.keys()) if self.layer.data_properties is not None else []
        )

        # add edit attributes that read properties
        edit_attributes = self.layer.edit_attributes
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
        if "filter" in self.layer.edit_attributes:  # new way
            filter_mapping = self.layer.edit_attributes["filter"]
            if filter_mapping.mapping_type != "enum":
                raise ValueError("Vector tiles filter is expected to be of type 'enum'")
            params["filter_key"] = filter_mapping.mapping_options["key"]
            params["filter"] = f"[{','.join(filter_mapping.mapping_options['values'])}]"
        elif "filter" in self.layer.mapbox_props:  # old way
            mapbox_filter = self.layer.mapbox_props["filter"]
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

