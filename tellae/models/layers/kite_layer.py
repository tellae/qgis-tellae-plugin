from qgis.core import (
    QgsProject,
    Qgis,
    QgsVectorTileBasicRendererStyle,
    QgsSymbol,
    QgsExpressionContextUtils,
)

from tellae.tellae_store import TELLAE_STORE
from tellae.models.layers.layer_style import ClassicStyle, VectorTilesStyle
from tellae.models.props_mapping import PropsMapping
from tellae.models.layers.layer_source import QgsLayerSource, GeojsonSource, SharkSource, VectorTileGeojsonSource

class LayerInitialisationError(Exception):
    pass

class MinZoomException(Exception):
    pass

class LayerStylingException(Exception):
    pass


class QgsKiteLayer:
    ACCEPTED_GEOMETRY_TYPES = []

    LAYER_VARIABLES = {}

    def __init__(
        self,
        layer_id,
        data,
        editAttributes=None,
        sourceType="geojson",
        layerProps=None,
        dataProperties=None,
        verbose=True,
        source_parameters=None,
        name="Unnamed",
        datasets=None,
        main_dataset=None,
        parent=None,
    ):
        # layer id
        self.id = layer_id

        # source instance
        self.source = None

        # Qgis layer instance
        self.qgis_layer = None

        # layer style instance
        self.style = None

        # parent layer instance
        self.parent_layer = parent

        # layer descriptive properties, used to determine layer display

        # layer name (displayed in Qgis legend)
        if isinstance(name, dict):
            self.name = name[TELLAE_STORE.locale]
        else:
            self.name = name

        # object used to determine layer contents
        self.data = data

        # type of data provided to the layer
        self.source_type = sourceType

        # additional parameters passed to source at layer creation
        self.source_parameters = source_parameters

        # description of the properties of the data
        self.data_properties = dataProperties if dataProperties is not None else dict()

        self.edit_attributes = editAttributes if editAttributes is not None else dict()
        self._read_edit_attributes()

        # datasets used by the data
        self.datasets = datasets if datasets is not None else []

        # main dataset used by the data
        self.main_dataset = main_dataset

        # additional mapbox properties
        self.mapbox_props = layerProps if layerProps is not None else dict()

        # util attributes

        # whether to display information with popup
        self.verbose = verbose
    #
    # def __init__(self, layer_data):
    #
    #     self.parent_layer = layer_data.get("parent", None)
    #
    #     self.id = layer_data["id"]
    #
    #     self.layerClass = layer_data["layer_class"]
    #
    #     self.data = layer_data.get("data", None)
    #
    #     self.sourceType = layer_data.get("sourceType", "geojson")
    #
    #     self.mapboxProps = layer_data.get("layerProps", dict())
    #
    #     self.dataProperties = layer_data.get("dataProperties", dict())
    #
    #     self.verbose = layer_data.get("verbose", True)
    #
    #     self.source_geometry = layer_data.get("source_geometry", None)
    #
    #     if "name" in layer_data:
    #         name = layer_data["name"]
    #         if isinstance(name, dict):
    #             self.name = name[TELLAE_STORE.locale]
    #         else:
    #             self.name = name
    #     else:
    #         self.name = "Unnamed"
    #
    #     self.datasets = layer_data.get("datasets", [])
    #     self.main_dataset = layer_data.get("main_dataset", None)
    #
    #     self.editAttributes = layer_data.get("editAttributes", dict())
    #     self._read_edit_attributes()
    #
    #     self.qgis_layer = None
    #
    #     self.style = None
    #
    #     self.source = None

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
        if self.source_type == "geojson":
            return GeojsonSource(self)
        elif self.source_type == "shark":
            return SharkSource(self)
        elif self.source_type == "vector":
            if TELLAE_STORE.get_current_scale() > 2000000:
                raise MinZoomException
            return VectorTileGeojsonSource(self)
        else:
            raise ValueError(f"Unsupported source type '{self.source_type}'")

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
        self.qgis_layer = self.source.create_qgis_layer_instance(**self.source_parameters)

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
            if key in self.data_properties:
                if isinstance(self.data_properties[key], dict):
                    alias = self.data_properties[key][TELLAE_STORE.locale]
                elif isinstance(self.data_properties[key], str):
                    alias = self.data_properties[key]
                else:
                    raise ValueError(
                        f"Unsupported dataProperty type: {type(self.data_properties[key])}"
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
        if self.edit_attributes is not None:
            self.edit_attributes = {
                key: PropsMapping.from_spec(key, spec) for key, spec in self.edit_attributes.items()
            }

    def infer_main_props_mapping(self):

        legend = None
        non_constant = None
        color = None

        for key in self.edit_attributes:
            mapping = self.edit_attributes[key]
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

