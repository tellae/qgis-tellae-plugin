from tellae.utils.utils import log
from tellae.utils.network_access_manager import (
    RequestsException,
    RequestsExceptionTimeout,
    RequestsExceptionConnectionError,
    RequestsExceptionUserAbort,
    UnauthorizedError,
)


class MinZoomException(Exception):
    pass


class LayerStylingException(Exception):
    pass
