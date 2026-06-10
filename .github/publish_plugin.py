from qgispluginci.release import upload_plugin_to_osgeo_with_token
from os import environ

upload_plugin_to_osgeo_with_token(
    environ["ARCHIVE_FILENAME"],
    "tellae",
    environ["PUBLISH_TOKEN"],
)
