
from qgis.core import (
    QgsApplication,
    QgsAuthMethodConfig,
    QgsProject,
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsVectorTileLayer,
    QgsMessageLog,
    QgsNetworkAccessManager,
    QgsBlockingNetworkRequest,
    QgsFeedback,
QgsNetworkContentFetcher,
QgsNetworkContentFetcherTask
)
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from .utils import log, AuthenticationError, read_local_config, RequestError, get_apikey_from_cache, create_auth_config, get_auth_config, remove_tellae_auth_config, CancelImportDialog
import os
import json

AWS_TELLAE_CONFIG = "AWS-Tellae"
AWS_TELLAE_DEV_CONFIG = "AWS-Tellae-dev"
AWS_TELLAE_TMP_CONFIG = "AWS-Tellae-tmp"

class TellaeStore:

    def __init__(self):
        # qgis network manager
        self.network_manager = QgsNetworkAccessManager.instance()

        self.network_fetcher = QgsNetworkContentFetcher()

        self.fetchers = []

        # self.network_fetcher.finished.connect(self.on_request_finish)

        # self.network_fetcher.errorOccurred.connect(self.on_request_error)

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

        def handler(response):
            if set_user:
                self.user = response

        self.request_whale("/auth/me", handler)

        return

        # save user info
        if set_user:
            self.user = response

    def init_store(self):

        if not self.authenticated:
            raise AuthenticationError("User need to be authenticated before the store is initiated")

        self.request_layer_summary()
        self.request_datasets_summary()

        self.store_initiated = True

    def on_request_error(self, error_code, error_msg):
        log("request error")
        log("error code " + str(error_code))
        log("error msg " + str(error_msg))

    def on_request_finish(self, fetcher, handler: callable, dialog=None, to_json=True):
        def on_finish():

            if dialog:
                dialog.done(0)
            log("request finish")

            log("was canceled: " + str(fetcher.wasCanceled()))
            if fetcher.wasCanceled():
                raise ValueError("Canceled")

            content = bytes(fetcher.reply().readAll())
            if content:
                if to_json:
                    content = json.loads(content)

            handler(content)

            self.fetchers.remove(fetcher)

        return on_finish



    def request(self, url, handler, auth_cfg=None, to_json=True, dialog=False):

        fetcher = QgsNetworkContentFetcher()

        self.fetchers.append(fetcher)

        if dialog:
            cancel_import_dialog = CancelImportDialog()

            def set_dialog_text(bytes_received, total_bytes):
                cancel_import_dialog.chunkLabel.setText(
                    "{}% downloaded".format(
                        round(float(bytes_received)/total_bytes*100),
                    )
                )

            fetcher.downloadProgress.connect(set_dialog_text)

            cancel_import_dialog.cancelButton.clicked.connect(fetcher.cancel)
        else:
            cancel_import_dialog = None

        fetcher.finished.connect(self.on_request_finish(fetcher, handler, cancel_import_dialog, to_json=to_json))
        fetcher.errorOccurred.connect(self.on_request_error)

        fetcher.fetchContent(QUrl(url), authcfg=auth_cfg)


        # TODO : manage callbacks






    def request_whale(self, url, handler, **kwargs):

        if url.startswith("https://"):
            raise ValueError("Only the relative path of the Whale url should be provided")

        # prepend whale endpoint
        whale_url = self.whale_endpoint + url

        # make the request using the AWS authentication
        self.request(whale_url, handler, auth_cfg=self.authCfg, **kwargs)

        return




        # blocking_request = QgsBlockingNetworkRequest()
        # blocking_request.setAuthCfg(self.authCfg)
        #
        # feedback = QgsFeedback()
        # blocking_request.downloadProgress.connect(self.log_download_content)
        request = QNetworkRequest(QUrl(self.whale_endpoint + url))

        error_code = blocking_request.get(request, feedback=feedback)



        log(QgsBlockingNetworkRequest.NetworkError)
        log(QgsBlockingNetworkRequest.NoError)
        log(QgsBlockingNetworkRequest.ServerExceptionError)
        log(QgsBlockingNetworkRequest.TimeoutError)

        if error_code == QgsBlockingNetworkRequest.NoError:
            response = bytes(blocking_request.reply().content())
            if to_json:
                response = json.loads(response)
        else:
            raise RequestError(error_code)

        return response


        response = self.network_manager.blockingGet(request, authCfg=self.authCfg)



        error_code = response.error()

        if error_code == QNetworkReply.NoError:
            response = bytes(response.content())
            if to_json:
                response = json.loads(response)
        elif error_code == QNetworkReply.NetworkError:
            raise ValueError("NetworkError")
        elif error_code == QNetworkReply.ServerExceptionError:
            raise ValueError("ServerExceptionError")
        elif error_code == QNetworkReply.TimeoutError:
            raise ValueError("TimeoutError ")
        else:
            raise RequestError(response)

        return response

    def request_layer_summary(self):

        def handler(response):
            layers = sorted(response, key=lambda x: x["name"]["fr"])
            self.layer_summary = layers

            themes = list(set([theme for layer in layers for theme in layer["themes"]]))

            self.themes = sorted(themes)

        self.request_whale("/shark/layers/table?ne_lng=180&ne_lat=90&sw_lng=-180&sw_lat=-90", handler)
        # layers = self.request_whale("/shark/layers/table")

        return

        layers = sorted(layers, key=lambda x: x["name"]["fr"])
        self.layer_summary = layers

        themes = list(set([theme for layer in layers for theme in layer["themes"]]))

        self.themes = sorted(themes)

    def request_datasets_summary(self):

        def handler(response):
            datasets = {dataset["id"]: dataset for dataset in response}

            self.datasets_summary = datasets

        self.request_whale("/shark/datasets/summary", handler)

        return

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