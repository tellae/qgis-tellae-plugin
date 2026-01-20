from qgis.core import (
    Qgis,
)
from tellae.tellae_store import TELLAE_STORE
from tellae.utils import log


class LayerItem:

    def __init__(self, name, verbose=True):
        # displayed name
        self._name: str | dict = name

        # whether to display information with popup
        self._verbose: bool | None = verbose

    def __str__(self):
        return f"{self.name} ({self.__class__.__name__})"

    @property
    def name(self) -> str:
        return self._name

    @property
    def verbose(self) -> bool:
        return self._verbose

    def popup(self, message: str, level: Qgis.MessageLevel):
        """
        Display a popup if the layer is tagged as verbose.

        :param message: popup message
        :param level: message priority level
        """
        # display a popup if verbose
        if self.verbose:
            TELLAE_STORE.main_dialog.display_message_bar(message, level=level)

    def log(self, message, level="NO_LEVEL"):
        """
        Log a message with the layer name as prefix.

        :param message: message to log
        :param level: message level
        """
        log(f"[{self}]: {message}", level=level)
