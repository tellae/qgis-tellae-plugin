# -*- coding: utf-8 -*-

import os
import webbrowser
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtWidgets import QDialogButtonBox, QDialog
from qgis.PyQt.QtCore import Qt

from tellae.tellae_store import TELLAE_STORE


# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "tellae_auth.ui"))


class TellaeAuthDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(TellaeAuthDialog, self).__init__(parent)

        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setup_dialog()

    def init_auth(self):
        try:
            TELLAE_STORE.init_auth()
        except Exception as e:
            self.display_error_message(str(e))
            self.open()

    def validate(self):
        try:
            TELLAE_STORE.try_new_indents(self.keyEdit.text(), self.secretEdit.text())
            self.done(QDialog.Accepted)
        except Exception as e:
            self.display_error_message(str(e))

    # def try_authenticate(self, apikey, secret, endpoint=None):
    #     message = ""
    #     try:
    #         TELLAE_STORE.authenticate(apikey, secret, endpoint=endpoint)
    #         self.accept()
    #     except RequestError as e:
    #         message = f"Erreur lors de la requête: {str(e)}"
    #     except requests.ConnectionError:
    #         message = "Le serveur distant ne répond pas"
    #     except EnvironmentError:
    #         message = "Erreur lors de la récupération des identifiants"
    #     except AuthenticationError:
    #         message = "Erreur d'authentification, vérifiez vos identifiants"
    #     except AccessError:
    #         message = "Vous n'avez pas accès à cette fonctionnalité"
    #     self.display_error_message(message)

    # def try_authenticate_from_inputs(self):
    #     self.try_authenticate(self.keyEdit.text(), self.secretEdit.text())

    def setup_dialog(self):
        self.helpButton.clicked.connect(self.open_help_page)
        self.cancelButton.clicked.connect(self.done)
        self.validateButton.clicked.connect(self.validate)

    def open_help_page():
        url = f"https://tellae.fr/#/blog/{TELLAE_STORE.locale}/kite_api_key"
        webbrowser.open(url)
    open_help_page = staticmethod(open_help_page)

    def display_error_message(self, message):
        self.errorMessage.setText(message)

    def set_indents_from_auth_config(self):
        apikey, secret = TELLAE_STORE.get_current_indents()

        if apikey is not None:
            # fill the text fields
            self.keyEdit.setText(apikey)
            self.secretEdit.setText(secret)
