# -*- coding: utf-8 -*-

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets

from .utils import log, create_new_tellae_auth_config

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'tellae_auth.ui'))


class TellaeAuthDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(TellaeAuthDialog, self).__init__(parent)
        log("INIT AUTH DIALOG")
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setup_auth_save()


    def setup_auth_save(self):
        log("SETUP SAVE")
        self.pushButton.clicked.connect(self.save_api_key)

    def save_api_key(self):
        log("SAVE API KEY")
        log(self.keyEdit.text())
        log(self.secretEdit.text())
        create_new_tellae_auth_config(self.keyEdit.text(), self.secretEdit.text())