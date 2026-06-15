"""
From QuickOSM plugin.
"""
from pathlib import Path

from qgis.core import QgsSettings
from qgis.PyQt.QtCore import QFileInfo, QLocale
from qgis.PyQt.QtWidgets import QApplication
from tellae.utils import log


def setup_translation(file_pattern="tellae_{}.qm", folder=None, force_locale=None):
    """Find the translation file according to locale.

    :param file_pattern: Custom file pattern to use to find QM files.
    :type file_pattern: basestring

    :param folder: Optional folder to look in if it's not the default.
    :type folder: basestring

    :param force_locale: force the translation locale
    :type force_locale: basestring

    :return: The locale and the file path to the QM file, or None.
    :rtype: (basestring, basestring)
    """
    locale = QgsSettings().value("locale/userLocale", QLocale().name()) if force_locale is None else force_locale

    if folder:
        ts_file = QFileInfo(str(Path(folder).joinpath(file_pattern.format(locale))))
    else:
        ts_file = QFileInfo("tellae/i18n/" + file_pattern.format(locale))

    if ts_file.exists():
        return locale, ts_file.absoluteFilePath()

    if folder:
        ts_file = QFileInfo(str(Path(folder).joinpath(file_pattern.format(locale[0:2]))))
    else:
        ts_file = QFileInfo("tellae/i18n/" + file_pattern.format(locale[0:2]))
    if ts_file.exists():
        return locale, ts_file.absoluteFilePath()

    return locale, None


def tr(text, context="@default"):
    return QApplication.translate(context, text)