
from ..utils import log

from qgis.core import (

    Qgis,
    QgsVectorTileBasicLabeling,
    QgsVectorTileBasicLabelingStyle,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsLabelPlacementSettings,
)


from PyQt5.QtGui import QColor


class LayerStyle:

    def __init__(self, layer):


        self.layer = layer

        self.originalRenderer = self.layer.qgis_layer.renderer()

        self.geometry_type = self.layer.GEOMETRY_TYPE

        self.min_zoom_level = None
        if "minzoom" in self.layer.mapboxProps:
            self.min_zoom_level = self.layer.mapboxProps["minzoom"]

        self.editAttributes = self.layer.editAttributes

        self.main_props_mapping = None
        if self.layer.editAttributes:
            self.main_props_mapping = self.layer.infer_main_props_mapping()

        self.secondary_mappings = [v for v in self.editAttributes.values() if v != self.main_props_mapping and v.paint]


    @property
    def layer_renderer(self):
        return self.layer.qgis_layer.renderer()

    def set_labelling(self, text_attribute):
        raise NotImplementedError


class VectorTilesStyle(LayerStyle):

    def update_layer(self):

        styles = self.create_styles()

        self.layer_renderer.setStyles(styles)


    def create_styles(self):

        styles = self.main_props_mapping.create_vector_tile_styles(self.geometry_type)

        for style in styles:
            for mapping in self.secondary_mappings:
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



        renderer = self.main_props_mapping.create_renderer(self.layer, self.geometry_type, self.secondary_mappings)

        self.layer.qgis_layer.setRenderer(renderer)





# def infer_symbol_prop(geometry_type: Qgis.GeometryType, paint_type: str):
#     if geometry_type == Qgis.GeometryType.Line:
#         if paint_type == "color":
#             return QgsSymbolLayer.PropertyStrokeColor
#         elif paint_type == "size":
#             return QgsSymbolLayer.PropertyStrokeWidth
#         else:
#             raise PaintTypeError
#     elif geometry_type == Qgis.GeometryType.Polygon:
#         if paint_type == "color":
#             return QgsSymbolLayer.PropertyFillColor
#         elif paint_type == "size":
#             log("Trying to use size paint on polygon layer")
#             return None
#         else:
#             raise PaintTypeError
#     elif geometry_type == Qgis.GeometryType.Point:
#         if paint_type == "color":
#             return QgsSymbolLayer.PropertyFillColor
#         elif paint_type == "size":
#             return QgsSymbolLayer.PropertySize
#         else:
#             raise PaintTypeError
#     else:
#         raise ValueError(f"Unsupported geometry type '{geometry_type}'")




# from math import exp, sqrt
#
# def linear_zoom_interpolation(prop_value, context : QgsExpressionContext=None):
#
#     zoom_level = context.variable("zoom_level")
#
#
#
#
#     result = 50 * sqrt(100 * prop_value / 3.14)

