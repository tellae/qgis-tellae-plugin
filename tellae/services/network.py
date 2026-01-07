from tellae.tellae_store import TELLAE_STORE
from tellae.utils import log
from tellae.utils.requests import request_whale
import copy


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
        blocking=True
    )["content"]["data"]["PublicTransports"]["results"]

    TELLAE_STORE.gtfs_list = gtfs_list
    TELLAE_STORE.main_dialog.network_panel.update_network_list()

def get_gtfs_routes_and_stops(gtfs_uuid, handler, error_handler):

    routes = request_whale(url=f"/public_transports/{gtfs_uuid}/gtfs_routes", error_handler=error_handler, blocking=True)["content"]["results"]
    stops = request_whale(url=f"/public_transports/{gtfs_uuid}/gtfs_stops", error_handler=error_handler, blocking=True)["content"]["results"]

    features = []
    for route in routes:
        properties_copy = copy.deepcopy(route)
        geometry_copy = properties_copy["geometry"]
        del properties_copy["geometry"]
        del properties_copy["statistics"]
        del properties_copy["gtfs"]
        del properties_copy["_creationDate"]
        del properties_copy["_lastUpdate"]

        features.append({
            "type": "Feature",
            "geometry": geometry_copy,
            "properties": properties_copy
        })

    for stop in stops:
        properties_copy = copy.deepcopy(stop)
        geometry_copy = properties_copy["geometry"]
        del properties_copy["geometry"]
        del properties_copy["statistics"]
        del properties_copy["gtfs"]
        del properties_copy["_creationDate"]
        del properties_copy["_lastUpdate"]

        features.append({
            "type": "Feature",
            "geometry": geometry_copy,
            "properties": properties_copy
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    handler(geojson)


