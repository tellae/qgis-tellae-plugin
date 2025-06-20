# -*- coding: utf-8 -*-

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtWidgets import QDialogButtonBox, QDialog
from qgis.PyQt.QtCore import Qt

from .utils import log, create_auth_config, get_apikey_from_cache, AuthenticationError, AccessError, read_local_config, RequestError, get_apikey_from_cache
from .tellae_store import TELLAE_STORE
import requests


# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'tellae_auth.ui'))


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
        # self.buttonBox.accepted.connect(self.validate)
        self.cancelButton.clicked.connect(self.done)
        self.validateButton.clicked.connect(self.validate)

    def display_error_message(self, message):
        self.errorMessage.setText(message)

    # def _check_local_config_existence(self):
    #     local_auth = False
    #     if TELLAE_STORE.local_config is not None and "auth" in TELLAE_STORE.local_config and TELLAE_STORE.local_config["auth"].get("use", True):
    #         local_auth = True
    #         log("Authentication from local configuration")
    #
    #         try:
    #             endpoint = TELLAE_STORE.local_config["auth"].get("WHALE_ENDPOINT", None)
    #             self.try_authenticate(TELLAE_STORE.local_config["auth"]["WHALE_API_KEY_ID"], TELLAE_STORE.local_config["auth"]["WHALE_SECRET_ACCESS_KEY"], endpoint=endpoint)
    #         except KeyError as e:
    #             self.display_error_message(f"Erreur lors de l'authentification locale, clé manquante: {str(e)}")
    #             return local_auth
    #
    #     return local_auth

    def set_indents_from_auth_config(self):
        apikey, secret = TELLAE_STORE.get_current_indents()

        if apikey is not None:
            # fill the text fields
            self.keyEdit.setText(apikey)
            self.secretEdit.setText(secret)