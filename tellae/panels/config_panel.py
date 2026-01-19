from tellae.panels.base_panel import BasePanel
from tellae.services.project import select_project, get_project_name
from tellae.utils.utils import log


class ConfigPanel(BasePanel):

    def __init__(self, main_dialog):
        super().__init__(main_dialog)

        self.selector_listener_deactivated = False

    def setup(self):
        # open authentication dialog on authButton click
        self.dlg.authButton.clicked.connect(self.store.auth_dialog.open)

        # add listener on project selection
        self.dlg.projectSelector.currentIndexChanged.connect(self.select_project_with_index)

        # add listener on project reload button
        self.dlg.reloadProjectBtn.clicked.connect(self.reload_project)

    def set_auth_button_text(self, user):
        if user is None:
            text = "Login"
        else:
            text = f'{user["firstName"]} {user["lastName"]}'

        self.dlg.authButton.setText(text)

    def fill_project_selector(self):
        names = [project["name"] for project in self.store.projects if project != "SEP"]

        # set list of layers
        self.selector_listener_deactivated = True
        self.dlg.projectSelector.addItems(names)
        if "SEP" in self.store.projects:
            self.dlg.projectSelector.insertSeparator(self.store.projects.index("SEP"))
        self.selector_listener_deactivated = False

    def select_project_with_index(self, index):
        if self.selector_listener_deactivated:
            return

        if index == -1:
            raise ValueError(f"Could not find the project with name")

        self.dlg.start_progress("Récupération des données du projet")
        select_project(self.store.projects[index]["uuid"])
        self.dlg.end_progress()

    def reload_project(self):
        if self.store.current_project is not None:
            self.dlg.start_progress("Récupération des données du projet")
            select_project(self.store.current_project["uuid"])
            self.dlg.end_progress()

    def on_project_update(self):
        self.dlg.projectDescription.setText(self.store.current_project.get("description", ""))
        self.selector_listener_deactivated = True
        self.dlg.projectSelector.setCurrentText(self.store.current_project_name)
        self.selector_listener_deactivated = False
