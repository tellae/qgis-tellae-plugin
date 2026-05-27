from tellae.tellae_store import TELLAE_STORE
from tellae.utils import log
from tellae.utils.requests import request_whale, request_whale_with_continuation_token
import copy
import datetime


def init_gtfs_list():
    try:
        gtfs_list = get_gtfs_graphql("")
        gtfs_list = [gtfs for gtfs in gtfs_list if gtfs["project"] is None and gtfs["public"]]

        # set result in store
        TELLAE_STORE.gtfs_list = gtfs_list

        # update ux
        TELLAE_STORE.main_dialog.network_panel.update_database_network_list()
    except Exception as e:
        raise ValueError("Erreur lors de la récupération de la base de GTFS") from e


def update_project_gtfs_list():
    try:
        project_gtfs = get_gtfs_graphql(f"project='{TELLAE_STORE.current_project['uuid']}'")

        # set result in store
        TELLAE_STORE.project_gtfs_list = project_gtfs

        # update ux
        TELLAE_STORE.main_dialog.network_panel.update_project_network_list()
    except Exception as e:
        raise ValueError("Erreur lors de la récupération des GTFS de l'utilisateur") from e

def get_gtfs_graphql(query: str):
    final_query = """
             query Q {
                 PublicTransports(query:"$query"){
                   results{
                      uuid
                      _creationDate
                      _lastUpdate
                      project {
                        name
                      }
                      name
                      moa{
                        uuid
                        name
                      }
                      moa_name
                      network_name
                      source
                      public
                      deprecated
                      status
                      _lastAnalysis {
                        _creationDate
                        uuid
                        status
                        statusDetails
                        errorMessage
                        config
                        _outputs
                        analysisVersion
                      }
                      analysisFrom {
                        _creationDate
                        uuid
                        status
                        statusDetails
                        errorMessage
                        config
                        _outputs
                        analysisVersion
                      }
                      dist_units
                      start_date
                      end_date
                      data
                      config
                      statistics
                      day_types
                      graphs
                   }
                 }
               }
         """.replace("$query", query)

    gtfs_list = request_whale(
        "/graphql",
        method="POST",
        headers={"content-type": "application/json"},
        body={"query": final_query},
        blocking=True,
    )["content"]["data"]["PublicTransports"]["results"]
    gtfs_list = [gtfs for gtfs in gtfs_list if not gtfs["deprecated"]]

    # sort by name and date
    gtfs_list = sorted(
        gtfs_list,
        key=lambda x: datetime.datetime.strptime(x.get("start_date", "1990-01-01") or "1990-01-01", "%Y-%M-%d"),
        reverse=True,
    )
    gtfs_list = sorted(gtfs_list, key=lambda x: x["name"])

    return gtfs_list

def get_gtfs_routes_and_stops(gtfs_uuid, handler, error_handler):

    routes = request_whale_with_continuation_token(
        url=f"/public_transports/{gtfs_uuid}/gtfs_routes",
        error_handler=error_handler,
    )
    stops = request_whale_with_continuation_token(
        url=f"/public_transports/{gtfs_uuid}/gtfs_stops",
        error_handler=error_handler,
    )

    route_features = []
    for route in routes:
        properties_copy = copy.deepcopy(route)
        geometry_copy = properties_copy["geometry"]
        del properties_copy["geometry"]
        del properties_copy["statistics"]
        del properties_copy["gtfs"]
        del properties_copy["_creationDate"]
        del properties_copy["_lastUpdate"]
        del properties_copy["uuid"]

        route_features.append(
            {"type": "Feature", "geometry": geometry_copy, "properties": properties_copy}
        )

    routes_geojson = {"type": "FeatureCollection", "features": route_features}

    stop_features = []
    for stop in stops:
        properties_copy = copy.deepcopy(stop)
        geometry_copy = properties_copy["geometry"]
        del properties_copy["geometry"]
        del properties_copy["statistics"]
        del properties_copy["gtfs"]
        del properties_copy["_creationDate"]
        del properties_copy["_lastUpdate"]
        del properties_copy["uuid"]

        stop_features.append(
            {"type": "Feature", "geometry": geometry_copy, "properties": properties_copy}
        )

    stops_geojson = {"type": "FeatureCollection", "features": stop_features}

    handler({"routes": routes_geojson, "stops": stops_geojson})


def gtfs_date_to_datetime(gtfs_date):
    res = datetime.datetime.strptime(gtfs_date, "%Y-%M-%d")
    return res.strftime("%d/%M/%Y")
