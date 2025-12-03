
from tellae.tellae_store import TELLAE_STORE
from tellae.utils import log
from tellae.utils.requests import request_whale, BlockingRequestError
from tellae.services.whale import download_from_binaries

def select_project(uuid: str):
    # check existence
    # project_uuids = [project.get("uuid") for project in TELLAE_STORE.user["_ownedProjects"]]
    # index = project_uuids.index(uuid)
    # if index == -1:
    #     raise ValueError(f"Could not find a project matching the uuid {uuid}")

    try:
        project = request_whale(f"/projects/{uuid}", blocking=True)["content"]

        # update store
        TELLAE_STORE.set_current_project(project)

        # update project data tables
        TELLAE_STORE.main_dialog.layers_panel.update_selected_project()

        # update project info
        TELLAE_STORE.main_dialog.config_panel.update_selected_project()
    except BlockingRequestError as e:
        log(f"An error occurred while trying to get project {uuid}: {e.message()}")


def get_project_binary_from_hash(binary_hash, attribute, handler, to_json=True):
    project_uuid = TELLAE_STORE.current_project["uuid"]
    index = get_binary_index_from_hash(binary_hash, attribute)
    if index == -1:
        raise ValueError("Error while to get project binary info")

    download_from_binaries(f"projects/{project_uuid}/{attribute}/{index}", handler=handler, to_json=to_json)


def get_binary_index_from_hash(binary_hash, attribute):
    hashes = [binary["hash"] for binary in TELLAE_STORE.current_project[attribute]]
    return hashes.index(binary_hash)




