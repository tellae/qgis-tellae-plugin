from tellae.utils.requests import request_whale, request
from tellae.utils import log


def download_from_binaries(info, handler, error_handler=None, to_json=True):

    def tmp_handler(result):
        # fetch the binary from the download url returned by whale
        fetch_url = result["content"]["Location"]
        request(fetch_url, handler=handler, error_handler=error_handler, to_json=to_json)

    # call whale to get a temporary download url
    request_whale(f"/binaries/{info}/url", handler=tmp_handler, error_handler=error_handler)
