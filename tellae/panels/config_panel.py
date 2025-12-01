from tellae.panels.base_panel import BasePanel
from tellae.services.project import select_project


class ConfigPanel(BasePanel):

    def __init__(self, main_dialog):
        super().__init__(main_dialog)

        self.project_names = []

    def setup(self):
        # open authentication dialog on authButton click
        self.dlg.authButton.clicked.connect(self.store.auth_dialog.open)

        # add listener on project selection
        self.dlg.projectSelector.currentTextChanged.connect(self.select_project_by_name)

    def set_auth_button_text(self, user):
        if user is None:
            text = "Login"
        else:
            text = f'{user["firstName"]} {user["lastName"]}'

        self.dlg.authButton.setText(text)

    def fill_project_selector(self):

        self.project_names = [project.get("name", "Mon projet") for project in self.store.user["_ownedProjects"]]

        # set list of layers
        self.dlg.projectSelector.addItems(self.project_names)

    def select_project_by_name(self, project_name):

        index = self.project_names.index(project_name)
        if index == -1:
            raise ValueError(f"Could not find the project with name {project_name}")

        select_project(self.store.user["_ownedProjects"][index]["uuid"])