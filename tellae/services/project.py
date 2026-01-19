from tellae.tellae_store import TELLAE_STORE
from tellae.utils import log
from tellae.utils.requests import request_whale, RequestsException
from tellae.utils.exceptions import InternalError
from tellae.services.whale import download_from_binaries
from qgis.core import Qgis


def update_project_list():
    try:
        user = TELLAE_STORE.user

        # get list of owned projects
        owned_projects = [
            {"uuid": project["uuid"], "name": get_project_name(project)}
            for project in user["_ownedProjects"]
        ]
        owned_projects = sorted(owned_projects, key=lambda x: x["name"])

        # get list of shared projects (can be empty
        shared_projects = [
            {"uuid": project["model"], "name": project["metadata"]["name"]}
            for project in user.get("_projects", [])
        ]
        shared_projects = sorted(shared_projects, key=lambda x: x["name"])

        # evaluate full list
        all_projects = owned_projects
        if len(shared_projects) > 0:
            all_projects = all_projects + ["SEP"] + shared_projects

        # update store
        TELLAE_STORE.projects = all_projects

        # update config panel
        TELLAE_STORE.main_dialog.config_panel.fill_project_selector()
    except Exception as e:
        raise ValueError("Erreur lors de la récupération de la liste des projets") from e


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
        TELLAE_STORE.main_dialog.layers_panel.on_project_update()
        TELLAE_STORE.main_dialog.flows_panel.on_project_update()

        # update project info
        TELLAE_STORE.main_dialog.config_panel.on_project_update()
    except Exception as e:
        raise ValueError("Erreur lors de la récupération du projet") from e


def get_project_binary_from_hash(binary_hash, attribute, handler, error_handler=None, to_json=True):
    project_uuid = TELLAE_STORE.current_project["uuid"]
    index = get_binary_index_from_hash(binary_hash, attribute)
    if index == -1:
        raise ValueError("Error while to get project binary info")

    download_from_binaries(
        f"projects/{project_uuid}/{attribute}/{index}",
        handler=handler,
        error_handler=error_handler,
        to_json=to_json,
    )


def get_binary_index_from_hash(binary_hash, attribute):
    hashes = [binary["hash"] for binary in TELLAE_STORE.current_project[attribute]]
    return hashes.index(binary_hash)


def get_project_name(project):
    return project.get("name", "Mon projet")
