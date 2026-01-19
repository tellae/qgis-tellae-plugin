from tellae.utils.network_access_manager import NetworkAccessManager, RequestsException
from tellae.utils.utils import log
from tellae.tellae_store import TELLAE_STORE
import json


def request(
    url,
    method="GET",
    body=None,
    handler=None,
    error_handler=None,
    headers=None,
    auth_cfg=None,
    to_json=True,
    blocking=False,
    raise_exception=True,
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
    :param blocking: whether the request is blocking (ie synchronous) or not
    :param raise_exception: whether to raise an exception on failed blocking requests

    :return:
    """

    # create a network access manager instance
    nam = NetworkAccessManager(authid=auth_cfg, debug=TELLAE_STORE.network_debug, timeout=0)

    # create callback function for async requests
    def on_finished():
        process_call_result(
            nam.httpResult(), to_json=to_json, handler=handler, error_handler=error_handler
        )

    try:
        # make request
        call_result, _ = nam.request(
            url, method=method, body=body, headers=headers, blocking=blocking
        )

        if not blocking:
            # add callback for asynchronous requests
            nam.reply.finished.connect(on_finished)
    except Exception as e:
        call_result = {
            "status": None,
            "status_code": None,
            "status_message": "Python error while making request",
            "content": None,
            "ok": False,
            "headers": None,
            "reason": "Python error while making request",
            "exception": e,
        }
        # call error handler on exception
        if not blocking and error_handler:
            error_handler(call_result)

    if blocking:
        if call_result["ok"]:
            return process_call_result(call_result, to_json=to_json)
        else:
            if raise_exception:
                raise call_result["exception"]
            else:
                return call_result
    else:
        return None


def request_whale(url, **kwargs):
    """
    Request Whale using the AWS authentication.

    :param url: requested whale service (url without the whale address)
    :param kwargs: see request function params
    """
    if url.startswith("https://"):
        raise ValueError("Only the relative path of the Whale url should be provided")

    if not url.startswith("/"):
        raise ValueError("Missing leading slash in Whale request")

    # prepend whale endpoint
    whale_url = TELLAE_STORE.whale_endpoint + url

    # make the request using the AWS authentication
    return request(whale_url, auth_cfg=TELLAE_STORE.authCfg, **kwargs)


def process_call_result(call_result, to_json, handler=None, error_handler=None):
    """
    Process request results based on success and request options.

    :param call_result: NetworkAccessManager return value
    :param to_json: whether to convert contents to json or not
    :param handler: handler for async requests
    :param error_handler: error handler for async requests
    :return:
    """
    # call handler depending on request success
    if call_result["ok"]:
        # convert request result to json
        if to_json:
            call_result["content"] = json.loads(call_result["content"])

        # call handler if provided
        if handler is not None:
            handler(call_result)
    elif not call_result["ok"] and error_handler:
        error_handler(call_result)

    return call_result


def message_from_request_error(result):
    status = result["status"]
    status_code = result["status_code"]
    status_message = result["status_message"]
    reason = result["reason"]
    return str(result["exception"])
