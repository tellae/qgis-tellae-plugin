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

    gtfs_list = request_whale(
        "/graphql",
        method="POST",
        headers={"content-type": "application/json"},
        body={"query": query},
        blocking=True
    )["content"]["data"]["PublicTransports"]["results"]

    TELLAE_STORE.gtfs_list = gtfs_list
    TELLAE_STORE.main_dialog.network_panel.update_network_list()

