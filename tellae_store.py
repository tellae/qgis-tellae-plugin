
from .tellae_client import requests as tellae_requests, binaries, version
from qgis.core import (
    QgsApplication,
    QgsAuthMethodConfig,
    QgsProject,
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsVectorTileLayer,
    QgsMessageLog,
    QgsNetworkAccessManager,
)
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from .utils import log, AuthenticationError, read_local_config, RequestError, get_apikey_from_cache, create_auth_config, get_auth_config, remove_tellae_auth_config
import os
import json

AWS_TELLAE_CONFIG = "AWS-Tellae"
AWS_TELLAE_DEV_CONFIG = "AWS-Tellae-dev"
AWS_TELLAE_TMP_CONFIG = "AWS-Tellae-tmp"

class TellaeStore:

    def __init__(self):
        # qgis network manager
        self.network_manager = QgsNetworkAccessManager.instance()



        # whale request manager
        self.whale_endpoint = "https://whale.tellae.fr"

        # authentication

        self.authCfg = None
        self.authName = None

        self.authenticated = False

        self.store_initiated = False

        # plugin data
        self.plugin_dir = os.path.dirname(__file__)

        # stored objects

        # authenticated user
        self.user = {}

        # full layer summary
        self.layer_summary = []

        self.themes = []

        # data datasets summary
        self.datasets_summary = {}

        # local config
        self.local_config = None
        self.read_local_config()

    def read_local_config(self):
        # store local configuration
        self.local_config = read_local_config(self.plugin_dir)


    def get_current_indents(self):
        return get_apikey_from_cache(self.authName)

    def init_auth(self):
        dev_auth = False
        if TELLAE_STORE.local_config is not None and "auth" in TELLAE_STORE.local_config and TELLAE_STORE.local_config["auth"].get("use", True):
            if "WHALE_ENDPOINT" in TELLAE_STORE.local_config["auth"]:
                self.whale_endpoint = TELLAE_STORE.local_config["auth"]["WHALE_ENDPOINT"]
            dev_auth = True

        # if dev authentification is required, use idents from local config
        if dev_auth:
            try:
                api_key = self.local_config["auth"]["WHALE_API_KEY_ID"]
                secret = self.local_config["auth"]["WHALE_SECRET_ACCESS_KEY"]
            except KeyError as e:
                raise ValueError(f"Erreur lors de l'authentification locale, clé manquante: {str(e)}")

            # create/set dev auth
            self.authenticate(
                api_key,
                secret,
                AWS_TELLAE_DEV_CONFIG
            )
        else:
            # try to get existing auth config
            cfg_id = get_auth_config(AWS_TELLAE_CONFIG)

            if cfg_id is not None:
                self.set_config(AWS_TELLAE_CONFIG, cfg_id)
                self.try_auth(set_user=True)
                self.authenticated = True


    def authenticate(self, key, secret, config_name=AWS_TELLAE_CONFIG):
        # try idents with a tmp config
        self.set_auth_config(AWS_TELLAE_TMP_CONFIG, key, secret)

        try:
            self.try_auth(set_user=True)
        except Exception as e:
            log("AUTHENTICATE EXCEPTION")
            log(str(e))
            raise e
        finally:
            remove_tellae_auth_config(AWS_TELLAE_TMP_CONFIG)

        # if indents are valid, set the asked config
        self.set_auth_config(config_name, key, secret)

        # validate authentification
        self.authenticated = True


    def set_auth_config(self, name, key, secret):
        auth_cfg = create_auth_config(
            name,
            key,
            secret
        )
        self.set_config(name, auth_cfg)

    def set_config(self, cfg_name, cfg_id):
        self.authCfg = cfg_id
        self.authName = cfg_name

    def try_auth(self, set_user=False):
        response = self.request_whale("/auth/me")

        # save user info
        if set_user:
            self.user = response

    def init_store(self):

        if not self.authenticated:
            raise AuthenticationError("User need to be authenticated before the store is initiated")

        self.request_layer_summary()
        self.request_datasets_summary()

        self.store_initiated = True

    def request_whale(self, url, method="GET", body=None):
        request = QNetworkRequest(QUrl(self.whale_endpoint + url))
        response = self.network_manager.blockingGet(request, authCfg=self.authCfg)

        if response.error() == QNetworkReply.NoError:
            response_json = json.loads(bytes(response.content()))
        else:
            raise RequestError(response)

        return response_json

    def request_layer_summary(self):
        # layers = self.request_whale("/shark/layers/table?ne_lng=180&ne_lat=90&sw_lng=-180&sw_lat=-90")
        layers = self.request_whale("/shark/layers/table")

        layers = sorted(layers, key=lambda x: x["name"]["fr"])
        self.layer_summary = layers

        themes = list(set([theme for layer in layers for theme in layer["themes"]]))

        self.themes = sorted(themes)

    def request_datasets_summary(self):
        datasets = self.request_whale("/shark/datasets/summary")

        datasets = {dataset["id"]: dataset for dataset in datasets}

        self.datasets_summary = datasets

    def get_filtered_layer_summary(self, selected_theme: str):

        if selected_theme == "Tous":
            return self.layer_summary
        else:
            return [layer for layer in self.layer_summary if selected_theme in layer["themes"]]

    def vector_tile_url(self, table_id):

        full_url = self.whale_endpoint + "/martin/" + table_id + "/{z}/{x}/{y}".replace("{", "%7B").replace("}", "%7D")
        # headers = self.request_manager._get_headers(full_url, "GET", None, "application/json", None)
        # uri = f"url={full_url}&type=xyz&http-header:Authorization={headers['Authorization']}&http-header:Content-Type={headers['Content-Type']}"

        uri = f"url={full_url}&type=xyz&authcfg={self.authCfg}"

        return uri


TELLAE_STORE = TellaeStore()