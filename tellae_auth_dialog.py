# -*- coding: utf-8 -*-

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets

from .utils import log, create_new_tellae_auth_config, get_apikey_from_cache, remove_tellae_auth_config, AuthenticationError, AccessError, read_local_config
from .tellae_store import TELLAE_STORE

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
        self.setup_auth_save()

        # remove existing environment variables
        # self.remove_auth_environment()

        if not self._check_local_config_existence():
            self._check_stored_auth_existence()

    def _check_local_config_existence(self):
        local_auth = False
        if TELLAE_STORE.local_config is not None and "auth" in TELLAE_STORE.local_config and TELLAE_STORE.local_config["auth"].get("use", True):
            local_auth = True
            log("Authentication from local configuration")

            try:
                for key in ["WHALE_API_KEY_ID", "WHALE_SECRET_ACCESS_KEY"]:
                    os.environ[key] = TELLAE_STORE.local_config["auth"][key]
            except KeyError as e:
                self.display_error_message(f"Erreur lors de l'authentification locale, clé manquante: {str(e)}")
                return local_auth

            self.try_authenticate()



        return local_auth

    def _check_stored_auth_existence(self):
        apikey, secret = get_apikey_from_cache()

        if apikey is not None:
            # fill the text fields
            self.keyEdit.setText(apikey)
            self.secretEdit.setText(secret)

            # set the environment variables from the text inputs
            self._set_environment_from_inputs()

            self.try_authenticate()

    def display_error_message(self, message):
        self.errorMessage.setText(message)

    def remove_auth_environment(self):
        for var in ["WHALE_API_KEY_ID", "WHALE_SECRET_ACCESS_KEY", "WHALE_ENDPOINT"]:
            if var in os.environ:
                os.environ.pop(var)

    def _set_environment_from_inputs(self):
        # set environment variables from text inputs
        os.environ["WHALE_API_KEY_ID"] = self.keyEdit.text()
        os.environ["WHALE_SECRET_ACCESS_KEY"] = self.secretEdit.text()

    def try_authenticate(self):
        message = ""
        try:
            # authenticate the TellaeStore
            TELLAE_STORE.authenticate()
        except EnvironmentError:
            message = "Erreur lors de la récupération des identifiants"
        except AuthenticationError:
            message = "Erreur d'authentification, vérifiez vos identifiants"
        except AccessError:
            message = "Vous n'avez pas accès à cette fonctionnalité"

        self.display_error_message(message)

    def setup_auth_save(self):
        log("SETUP SAVE")
        self.pushButton.clicked.connect(self.validate)

    def validate(self):
        log("SAVE API KEY")
        log(self.keyEdit.text())
        log(self.secretEdit.text())

        # try to authenticate from inputs
        self.authenticate_from_inputs()

        if TELLAE_STORE.authenticated:
            # save credentials if asked to
            if self.saveIndentsCheckBox.isChecked():
                create_new_tellae_auth_config(self.keyEdit.text(), self.secretEdit.text())

            # TODO: go back to main dialog