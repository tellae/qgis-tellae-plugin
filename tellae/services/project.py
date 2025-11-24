
from tellae.tellae_store import TELLAE_STORE
from tellae.utils import log
from tellae.utils.requests import request_whale
from tellae.services.whale import download_from_binaries

def select_project(uuid: str):
    project_uuids = [project.get("uuid") for project in TELLAE_STORE.user["_ownedProjects"]]
    index = project_uuids.index(uuid)
    if index == -1:
        raise ValueError(f"Could not find a project matching the uuid {uuid}")

    def handler(result):
        project = result["content"]

        # update store
        TELLAE_STORE.set_current_project(project)

        # update main dialog button
        TELLAE_STORE.main_dialog.projectsButton.setText(TELLAE_STORE.current_project_name)

        # update project dialog
        projects_dialog = TELLAE_STORE.projects_dialog
        projects_dialog.projectName.setText(TELLAE_STORE.current_project_name)
        projects_dialog.projectDescription.setText(project.get("description", ""))
        projects_dialog.projectSelector.setCurrentText(uuid)
        projects_dialog.set_project_data()

    request_whale(f"/projects/{uuid}", handler=handler)



def get_project_binary_from_hash(binary_hash, attribute, handler, to_json=True):
    project_uuid = TELLAE_STORE.current_project["uuid"]
    index = get_binary_index_from_hash(binary_hash, attribute)
    if index == -1:
        raise ValueError("Error while to get project binary info")

    download_from_binaries(f"projects/{project_uuid}/{attribute}/{index}", handler=handler, to_json=to_json)


def get_binary_index_from_hash(binary_hash, attribute):
    hashes = [binary["hash"] for binary in TELLAE_STORE.current_project[attribute]]
    return hashes.index(binary_hash)




