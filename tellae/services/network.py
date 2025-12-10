from tellae.tellae_store import TELLAE_STORE
from tellae.utils import log
from tellae.utils.requests import request_whale, RequestsException
from tellae.services.whale import download_from_binaries


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

    log(query)

    gtfs_list = request_whale("/graphql", method="POST", body={
        "query": query
    }, blocking=True)["data"]["PublicTransports"]["results"]

    log([gtfs["uuid"] for gtfs in gtfs_list])

    TELLAE_STORE.gtfs_list = gtfs_list

