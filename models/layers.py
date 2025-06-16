import tempfile
import requests
from abc import ABC, abstractmethod

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsVectorTileLayer,
)

from ..utils import log
from ..tellae_store import TELLAE_STORE
from .layer_styles import PropsMapping, ClassicStyle, VectorTilesStyle

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
        TELLAE_STORE.tellae_services.display_message(f"Erreur lors de l'ajout de la couche '{self.layer_name}': {str(exception)}")

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
        return TELLAE_STORE.vector_tile_url(self.layer.data)

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

        self._create_style()

        self._update_style()

        self._add_to_project()

    def _add_to_project(self):
        QgsProject.instance().addMapLayer(self.qgis_layer)

    def _read_edit_attributes(self):
        log(self.editAttributes)
        if self.editAttributes is not None:
            self.editAttributes = {key: PropsMapping.from_spec(key, spec) for key, spec in self.editAttributes.items()}


class KiteSymbolLayer(QgsKiteLayer):

    def _call_style_update(self):

        assert self.style.main_props_mapping.paint_type == "text", "KiteSymbolLayer mapping should have 'text' paint type"

        self.style.set_labelling(self.style.main_props_mapping.mapping_options["key"])


def create_layer(layer_data):
    layer_data = {
        **layer_data,
        **layer_data.get("additionalProperties", dict())
    }

    layer_class = layer_data["layer_class"]

    if layer_class in LAYER_CLASSES:
        layer_constructor = LAYER_CLASSES[layer_class]
    else:
        layer_constructor = LAYER_CLASSES["default"]

    layer_instance = layer_constructor.__new__(layer_constructor)
    layer_instance.__init__(layer_data)

    return layer_instance


LAYER_CLASSES = {
    "default": QgsKiteLayer,
    "KiteSymbolLayer": KiteSymbolLayer
}