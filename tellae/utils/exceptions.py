"""
Exceptions used by the plugin
"""

# generic exceptions

class InternalError(Exception):

    def __init__(self, message):
        super().__init__("Une erreur interne est survenue")
        self.__cause__ = RuntimeError(message)


# layer exceptions

class LayerInitialisationError(Exception):
    pass


class MinZoomException(Exception):
    pass


class LayerStylingException(Exception):
    pass


class EmptyLayerException(Exception):
    pass


# request exceptions

class RequestsException(Exception):
    pass

class RequestsExceptionTimeout(RequestsException):
    pass


class RequestsExceptionConnectionError(RequestsException):
    pass


class RequestsExceptionUserAbort(RequestsException):
    pass


class UnauthorizedError(RequestsException):
    pass


class BlockingRequestError(Exception):
    def __init__(self, call_result):
        self.result = call_result