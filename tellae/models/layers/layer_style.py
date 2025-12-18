from tellae.utils import log

from qgis.core import (
    Qgis,
    QgsVectorTileBasicLabeling,
    QgsVectorTileBasicLabelingStyle,
    QgsVectorLayerSimpleLabeling,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsLabelPlacementSettings,
    QgsSymbol,
    QgsNullSymbolRenderer,
)


from PyQt5.QtGui import QColor


class LayerStyle:
    """
    A class for updating the style of QGIS layers.

    This class updates the layer symbology and/or labelling
    according to the layer type (vector or vector tiles)
    using the mappings contained in the layer's editAttributes.
    """

    def __init__(self, layer):
        self.layer = layer

        self.originalRenderer = self.layer.qgis_layer.renderer()

        self.min_zoom_level = None
        if "minzoom" in self.layer.mapboxProps:
            self.min_zoom_level = self.layer.mapboxProps["minzoom"]

        self.editAttributes = self.layer.editAttributes

        self.main_props_mapping = None
        if self.layer.editAttributes:
            self.main_props_mapping = self.layer.infer_main_props_mapping()

        self.secondary_mappings = [
            v for v in self.editAttributes.values() if v != self.main_props_mapping and v.paint
        ]

    @property
    def layer_renderer(self):
        return self.layer.qgis_layer.renderer()

    def update_layer_symbology(self):
        """
        Set the symbols used to render the layer.
        """
        raise NotImplementedError

    def update_layer_labelling(self, text_attribute: str):
        """
        Set the labels displayed on the layer.

        :param text_attribute: property containing the text to display for each feature
        """
        raise NotImplementedError

    def remove_symbology(self):
        raise NotImplementedError


class ClassicStyle(LayerStyle):
    """
    A class for updating the style of classic QGIS vector layers.
    """

    def update_layer_symbology(self):
        # create a new renderer that reflects the rendering behaviour of the main mapping (constant, category, continuous..)
        renderer = self.main_props_mapping.create_renderer(
            self.layer, self.update_symbol_with_secondary_mappings
        )
        self.layer.qgis_layer.setRenderer(renderer)

    def update_symbol_with_secondary_mappings(self, symbol: QgsSymbol):
        """
        Update a symbol from the secondary mappings.

        This method is used to update symbols of the main mapping (for instance
        symbols of a QgsCategorizedSymbolRenderer) with other paint aspects.

        :param symbol: QgsSymbol instance
        """
        for mapping in self.secondary_mappings:
            mapping.update_symbol(symbol, self.layer)

    def update_layer_labelling(self, text_attribute: str):

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

        labeling = QgsVectorLayerSimpleLabeling(label_settings)

        self.layer.qgis_layer.setLabeling(labeling)
        self.layer.qgis_layer.setLabelsEnabled(True)

    def remove_symbology(self):
        # use a QgsNullSymbolRenderer instance
        renderer = QgsNullSymbolRenderer()
        self.layer.qgis_layer.setRenderer(renderer)


class VectorTilesStyle(LayerStyle):
    """
    A class for updating the style of QGIS vector tiles layers.
    """

    def update_layer_symbology(self):
        # create vector tile styles
        styles = self.create_vector_tiles_styles()
        self.layer_renderer.setStyles(styles)

    def create_vector_tiles_styles(self):
        # create a set of styles (a rule + a symbol) that reflect the rendering behaviour of the main mapping
        styles = self.main_props_mapping.create_vector_tile_styles(self.layer)

        # update each style with the rest of the mappings
        for style in styles:
            for mapping in self.secondary_mappings:
                mapping.update_symbol(style.symbol(), self.layer)

        return styles

    def update_layer_labelling(self, text_attribute):

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

    def remove_symbology(self):
        # disable default rendering styles of the layer
        rendering_styles = self.layer_renderer.styles()
        for style in rendering_styles:
            style.setEnabled(False)

        self.layer_renderer.setStyles(rendering_styles)
