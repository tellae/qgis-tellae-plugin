from tellae.panels.base_panel import BasePanel
from tellae.services.project import select_project


class ConfigPanel(BasePanel):

    def setup(self):
        # open authentication dialog on authButton click
        self.dlg.authButton.clicked.connect(self.store.auth_dialog.open)

        # add listener on project selection
        self.dlg.projectSelector.currentTextChanged.connect(select_project)

    def set_auth_button_text(self, user):
        if user is None:
            text = "Login"
        else:
            text = f'{user["firstName"]} {user["lastName"]}'

        self.dlg.authButton.setText(text)

    def fill_project_selector(self):
        project_names = [project.get("uuid") for project in self.store.user["_ownedProjects"]]

        # set list of layers
        self.dlg.projectSelector.addItems(project_names)