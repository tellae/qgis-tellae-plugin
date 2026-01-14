class InternalError(Exception):

    def __init__(self, message):
        super().__init__("Une erreur interne est survenue")
        self.__cause__ = RuntimeError(message)
