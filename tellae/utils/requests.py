from tellae.utils.network_access_manager import NetworkAccessManager

from tellae.tellae_store import TELLAE_STORE
import json


def request(
        url,
        method="GET",
        body=None,
        handler=None,
        error_handler=None,
        auth_cfg=None,
        to_json=True,
):
    """
    Make a network request using a NetworkAccessManager instance.

    :param url: request url
    :param method: request method
    :param body: request body
    :param handler: handler called on request success
    :param error_handler: handler called on request fail
    :param auth_cfg: Qgis authentication config (used to request with auth headers)
    :param to_json: convert response content to json
    """

    # create a network access manager instance
    nam = NetworkAccessManager(authid=auth_cfg, debug=TELLAE_STORE.network_debug, timeout=0)

    # create callback function: call handler depending on request success
    def on_finished():

        result = nam.httpResult()
        if result["ok"] and handler:
            # convert request result to json
            if to_json:
                result["content"] = json.loads(result["content"])
            handler(result)
        elif not result["ok"] and error_handler:
            error_handler(result)

    try:
        # make async request
        nam.request(url, method=method, body=body, blocking=False)

        # add callback
        nam.reply.finished.connect(on_finished)
    except Exception as e:
        # call error handler on exception
        if error_handler:
            error_handler(
                {
                    "status": None,
                    "status_code": None,
                    "status_message": "Python error while making request",
                    "content": None,
                    "ok": False,
                    "headers": None,
                    "reason": "Python error while making request",
                    "exception": e,
                }
            )

def request_whale(url, **kwargs):
    """
    Request Whale using the AWS authentication.

    :param url: requested whale service (url without the whale address)
    :param kwargs: see request function params
    """
    if url.startswith("https://"):
        raise ValueError("Only the relative path of the Whale url should be provided")

    # prepend whale endpoint
    whale_url = TELLAE_STORE.whale_endpoint + url

    # make the request using the AWS authentication
    return request(whale_url, auth_cfg=TELLAE_STORE.authCfg, **kwargs)


def message_from_request_error(result):
    status = result["status"]
    status_code = result["status_code"]
    status_message = result["status_message"]
    reason = result["reason"]
    return str(result["exception"])