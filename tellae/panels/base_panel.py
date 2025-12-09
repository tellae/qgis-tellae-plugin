from abc import ABC, abstractmethod

from tellae.tellae_store import TELLAE_STORE


class BasePanel(ABC):

    def __init__(self, main_dialog):

        self.dlg = main_dialog
        self.store = TELLAE_STORE

    @abstractmethod
    def setup(self):
        raise NotImplementedError
