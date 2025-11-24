# -*- coding: utf-8 -*-

import os
import webbrowser
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtWidgets import QPushButton
from qgis.PyQt.QtCore import Qt

from tellae.tellae_store import TELLAE_STORE
from tellae.utils.utils import getBinaryName, fill_table_widget, log
from tellae.services.project import select_project, get_project_binary_from_hash
from tellae.models.layers import create_custom_layer

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "projects_dialog.ui"))


class ProjectsDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(ProjectsDialog, self).__init__(parent)

        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setup_dialog()



    def setup_dialog(self):
        pass

        # self.helpButton.clicked.connect(self.open_help_page)
        # self.cancelButton.clicked.connect(self.done)
        # self.validateButton.clicked.connect(self.validate)

    def setup_project_selector(self):
        project_names = [project.get("uuid") for project in TELLAE_STORE.user["_ownedProjects"]]

        # set list of layers
        self.projectSelector.addItems(project_names)

        # add listener on update event
        self.projectSelector.currentTextChanged.connect(select_project)

    def set_project_data(self):

        table = self.table

        spatial_data = TELLAE_STORE.current_project["spatial_data"]

        def action_slot(table_widget, row_ix, col_ix, _, __):
            btn = QPushButton(table_widget)
            btn.setText("Add")
            btn.clicked.connect(lambda state, x=row_ix: self.add_spatial_data(x))
            table_widget.setCellWidget(row_ix, col_ix, btn)

        # setup table headers
        # total table length is 721, scroll bar is 16 => header width must total to 705
        headers = [
            {"text": "Nom", "value": lambda x: getBinaryName(x, with_extension=False), "width": 425},
            {"text": "Actions", "value": "actions", "width": 60, "slot": action_slot},
        ]

        fill_table_widget(table, headers, spatial_data)


    def add_spatial_data(self, row_idx):
        binary = TELLAE_STORE.current_project["spatial_data"][row_idx]
        name = getBinaryName(binary, with_extension=False)

        def handler(result):
            try:

                log(type(result["content"]))
                qgs_kite_layer = create_custom_layer(result["content"], name)
                qgs_kite_layer.add_to_qgis()

            except Exception as e:
                log(e)
                # TELLAE_STORE.main_dialog.signal_end_of_layer_add(name, e)
                raise e


        get_project_binary_from_hash(binary["hash"], "spatial_data", handler, to_json=False)