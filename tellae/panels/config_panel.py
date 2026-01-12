from tellae.panels.base_panel import BasePanel
from tellae.services.project import select_project
from tellae.utils.utils import log


class ConfigPanel(BasePanel):

    def __init__(self, main_dialog):
        super().__init__(main_dialog)

        self.project_names = []
        self.ongoing_project_selector_fill = False

    def setup(self):
        # open authentication dialog on authButton click
        self.dlg.authButton.clicked.connect(self.store.auth_dialog.open)

        # add listener on project selection
        self.dlg.projectSelector.currentIndexChanged.connect(self.select_project_by_name)

        # add listener on project reload button
        self.dlg.reloadProjectBtn.clicked.connect(self.reload_project)

    def set_auth_button_text(self, user):
        if user is None:
            text = "Login"
        else:
            text = f'{user["firstName"]} {user["lastName"]}'

        self.dlg.authButton.setText(text)

    def fill_project_selector(self):

        self.project_names = [
            project.get("name", "Mon projet") for project in self.store.user["_ownedProjects"]
        ]

        # set list of layers
        self.ongoing_project_selector_fill = True
        self.dlg.projectSelector.addItems(self.project_names)
        self.ongoing_project_selector_fill = False

    def select_project_by_name(self, index):
        if self.ongoing_project_selector_fill:
            return

        if index == -1:
            raise ValueError(f"Could not find the project with name")

        self.dlg.start_progress("Récupération des données du projet")
        select_project(self.store.user["_ownedProjects"][index]["uuid"])
        self.dlg.end_progress()

    def reload_project(self):
        if self.store.current_project is not None:
            self.dlg.start_progress("Récupération des données du projet")
            select_project(self.store.current_project["uuid"])
            self.dlg.end_progress()

    def update_selected_project(self):
        self.dlg.projectDescription.setText(self.store.current_project.get("description", ""))
        self.dlg.projectSelector.setCurrentText(self.store.current_project_name)
