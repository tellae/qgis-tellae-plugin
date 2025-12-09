from qgispluginci.release import upload_plugin_to_osgeo
from os import environ

upload_plugin_to_osgeo(
    environ["OSGEO_USERNAME"], environ["OSGEO_PASSWORD"], environ["ARCHIVE_FILENAME"]
)
