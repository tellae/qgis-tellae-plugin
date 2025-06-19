import tempfile
from abc import ABC, abstractmethod
import urllib.parse

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsVectorTileLayer,
Qgis
)

from ..utils import log
from ..tellae_store import TELLAE_STORE
from .layer_styles import ClassicStyle, VectorTilesStyle
from .props_mapping import PropsMapping

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

    def init_qgis_layer(self):
        # make a web request and read the geojson result as bytes
        TELLAE_STORE.request(self.url, handler=self.on_download, to_json=False)

    def on_download(self, response):
        # store request response
        self.response = response["content"]

        if self.response is None:
            log("Missing response for layer creation !")
        else:
            # call QGIS layer creation and add
            self._set_qgis_layer()

    def on_download_error(self, response):
        exception = response["exception"]
        TELLAE_STORE.main_dialog.display_message(f"Erreur lors de l'ajout de la couche '{self.layer_name}': {str(exception)}")

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

    def download_geojson(self):
        # make a request to whale and read the geojson result as bytes
        TELLAE_STORE.request_whale(self.url, handler=self.on_download, to_json=False)


class VectorTileSource(QgsLayerSource):

    @property
    def url(self):
        whale_endpoint = TELLAE_STORE.whale_endpoint
        auth_cfg = TELLAE_STORE.authCfg

        params = {
            "table": self.layer.data
        }

        # evaluate selected properties

        # start with properties from dataProperties
        select = list(self.layer.dataProperties.keys()) if self.layer.dataProperties is not None else []

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
            log(select)
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
        martin_url = (whale_endpoint +
                      "/martin/table_selection/{z}/{x}/{y}".replace("{", "%7B").replace("}", "%7D") +
                      f"?{urllib.parse.urlencode(params, safe='[]').replace('&', '%26')}")

        # build final uri (with url type and auth config)
        uri = f"url={martin_url}&type=xyz&authcfg={auth_cfg}"

        return uri

    def init_qgis_layer(self):
        # nothing to download, just create the instance with the correct vector tiles url
        self._set_qgis_layer()

    def _new_qgis_layer_instance(self):
        return QgsVectorTileLayer(self.url, self.layer_name)



class QgsKiteLayer:

    def __init__(self, layer_data):



        self.id = layer_data["id"]

        self.layerClass = layer_data["layer_class"]

        self.data = layer_data.get("data", None)

        self.sourceType = layer_data.get("sourceType", "geojson")

        self.mapboxProps = layer_data.get("layerProps", dict())

        self.dataProperties = layer_data.get("dataProperties", None)

        self.category = layer_data.get("category", None)

        self.name = layer_data.get("name", dict()).get("fr", "Unnamed")

        self.datasets = layer_data.get("datasets", [])
        self.main_dataset = layer_data.get("main_dataset", None)

        # TODO: what data structure
        self.filter = layer_data.get("filter", None)

        self.editAttributes = layer_data.get("editAttributes", None)
        self._read_edit_attributes()

        self.qgis_layer = None

        self.style = None

        self.source = self._init_source()

    @property
    def is_vector(self):
        return self.sourceType == "vector"

    def _init_source(self) -> QgsLayerSource:
        if self.sourceType == "geojson":
            return GeojsonSource(self)
        elif self.sourceType == "shark":
            return SharkSource(self)
        elif self.sourceType == "vector":
            return VectorTileSource(self)
        else:
            raise ValueError(f"Unsupported source type '{self.sourceType}'")

    def _set_qgis_layer(self, qgis_layer):
        self.qgis_layer = qgis_layer

    def _create_style(self):
        if self.is_vector:
            style = VectorTilesStyle(self)
        else:
            style = ClassicStyle(self)
        self.style = style

    def _update_style(self):
        self._call_style_update()

    def _call_style_update(self):
        if self.style.editAttributes:
            self.style.update_layer()

    def add_to_qgis(self):
        self.source.init_qgis_layer()

    def _add_to_qgis(self):
        log("_add_to_qgis")

        try:
            self._create_style()

            self._update_style()

            self._add_to_project()

            TELLAE_STORE.main_dialog.display_message(f"La couche '{self.name}' a été ajoutée avec succès !")
        except Exception as e:
            TELLAE_STORE.main_dialog.display_message(f"Erreur lors de l'ajout de la couche '{self.name}': {str(e)}")

    def _add_to_project(self):
        QgsProject.instance().addMapLayer(self.qgis_layer)

    def _read_edit_attributes(self):
        log(self.editAttributes)
        if self.editAttributes is not None:
            self.editAttributes = {key: PropsMapping.from_spec(key, spec) for key, spec in self.editAttributes.items()}

class KiteCircleLayer(QgsKiteLayer):
    GEOMETRY_TYPE = Qgis.GeometryType.Point

class KiteSymbolLayer(QgsKiteLayer):

    GEOMETRY_TYPE = Qgis.GeometryType.Point

    def _call_style_update(self):

        assert self.style.main_props_mapping.paint_type == "text", "KiteSymbolLayer mapping should have 'text' paint type"

        self.style.set_labelling(self.style.main_props_mapping.mapping_options["key"])

class KiteLabelLayer(QgsKiteLayer):
    GEOMETRY_TYPE = Qgis.GeometryType.Point

class KiteLineLayer(QgsKiteLayer):
    GEOMETRY_TYPE = Qgis.GeometryType.Line

class KiteFillLayer(QgsKiteLayer):
    GEOMETRY_TYPE = Qgis.GeometryType.Polygon


def create_layer(layer_data):
    layer_data = {
        **layer_data,
        **layer_data.get("additionalProperties", dict())
    }

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
    "KiteSymbolLayer": KiteSymbolLayer,
    "KiteLabelLayer": KiteLabelLayer,
    "KiteLineLayer": KiteLineLayer,
    "KiteFillLayer": KiteFillLayer
}