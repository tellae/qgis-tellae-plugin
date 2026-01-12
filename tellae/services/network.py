from tellae.tellae_store import TELLAE_STORE
from tellae.utils import log
from tellae.utils.requests import request_whale
import copy
import datetime


def init_gtfs_list():

    query = """
            query Q {
                PublicTransports(query:"status='READY'"){
                  results{
                    uuid
                    pt_network{
                      uuid
                      moa{
                        uuid
                        name
                      }
                      name
                    }
                    statistics
                    start_date
                    end_date
                    day_types
                  }
                }
              }
        """

    gtfs_list = request_whale(
        "/graphql",
        method="POST",
        headers={"content-type": "application/json"},
        body={"query": query},
        blocking=True,
    )["content"]["data"]["PublicTransports"]["results"]

    # evaluate and store name
    for gtfs in gtfs_list:
        gtfs["name"] = gtfs_name(gtfs)

    # sort by name and date
    gtfs_list = sorted(
        gtfs_list,
        key=lambda x: datetime.datetime.strptime(x["start_date"], "%Y-%M-%d"),
        reverse=True,
    )
    gtfs_list = sorted(gtfs_list, key=lambda x: x["name"])

    # set result in store
    TELLAE_STORE.gtfs_list = gtfs_list

    # update ux
    TELLAE_STORE.main_dialog.network_panel.update_network_list()


def get_gtfs_routes_and_stops(gtfs_uuid, handler, error_handler):

    routes = request_whale(
        url=f"/public_transports/{gtfs_uuid}/gtfs_routes",
        error_handler=error_handler,
        blocking=True,
    )["content"]["results"]
    stops = request_whale(
        url=f"/public_transports/{gtfs_uuid}/gtfs_stops", error_handler=error_handler, blocking=True
    )["content"]["results"]

    route_features = []
    for route in routes:
        properties_copy = copy.deepcopy(route)
        geometry_copy = properties_copy["geometry"]
        del properties_copy["geometry"]
        del properties_copy["statistics"]
        del properties_copy["gtfs"]
        del properties_copy["_creationDate"]
        del properties_copy["_lastUpdate"]

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

        stop_features.append(
            {"type": "Feature", "geometry": geometry_copy, "properties": properties_copy}
        )

    stops_geojson = {"type": "FeatureCollection", "features": stop_features}

    handler({"routes": routes_geojson, "stops": stops_geojson})


def gtfs_name(gtfs):
    return f'{gtfs["pt_network"]["moa"]["name"]} ({gtfs["pt_network"]["name"]})'


def gtfs_date_to_datetime(gtfs_date):
    res = datetime.datetime.strptime(gtfs_date, "%Y-%M-%d")
    return res.strftime("%d/%M/%Y")
