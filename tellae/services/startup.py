
from tellae.tellae_store import TELLAE_STORE
from tellae.utils import log
from tellae.services.layers import init_layers_table

def init_store():
    if not TELLAE_STORE.authenticated:
        log("Trying to initiate store without being authenticated")
        return

    init_layers_table()

    TELLAE_STORE.store_initiated = True