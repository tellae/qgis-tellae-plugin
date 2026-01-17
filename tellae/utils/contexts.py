from tellae.tellae_store import TELLAE_STORE
from tellae.utils import log
from qgis.core import Qgis


# basic progress context


class ProgressContext:
    """
    Basic context manager displaying the progress bar with a static message.

    Displays a popup upon error.
    """

    def __init__(self, progress_text):

        self.progress_text = progress_text

    def signal_error_without_interrupting(self, exc):
        """
        Signal that an error without interrupting the progress.

        :param exc: Exception instance
        """
        self._signal_error(exc)

    def __enter__(self):
        # start progress
        TELLAE_STORE.main_dialog.start_progress(self.progress_text)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # signal error
        if exc_type is not None:
            self._signal_error(exc_val)

        # end progress
        TELLAE_STORE.main_dialog.end_progress()

        return True

    def _signal_error(exc):
        """
        Signal error by displaying a snackbar and logging the error message and trace.

        :param exc: Exception instance
        """
        TELLAE_STORE.main_dialog.message_bar_from_exception(exc)

    _signal_error = staticmethod(_signal_error)


# layer download context


class LayerDownloadContext:

    def __init__(self, layer_name, handler, error_handler=None):

        self.layer_name = layer_name

        self.handler = self._evaluate_handler(handler)

        self.error_handler = self._evaluate_error_handler(error_handler)

        self.download_successful = False

    def _evaluate_handler(self, handler):
        def final_handler(result):
            # mark layer download as successful
            self.download_successful = True

            # signal end of download
            _end_of_layer_download()

            handler(result)

        return final_handler

    def _evaluate_error_handler(self, error_handler):
        return _layer_download_error_handler(self.layer_name, error_handler)

    def __enter__(self):
        # signal start of layer download
        _start_of_layer_download(self.layer_name)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if not self.download_successful:
                # call handler if error occurred within context and download has not successfully ended
                self.error_handler(exc_val)

        return not self.download_successful


# utils for layer download context


def _layer_download_error_handler(layer_name, error_handler=None):
    def final_handler(result):
        log(f"Error while downloading '{layer_name}': {result['exception']}", "CRITICAL")
        log(result, "CRITICAL")
        TELLAE_STORE.main_dialog.display_message_bar(
            f"Erreur lors du téléchargement de la couche '{layer_name}': {result['status_code']} ({result['status_message']})",
            level=Qgis.MessageLevel.Critical,
        )

        _end_of_layer_download()

        if error_handler is not None:
            error_handler(result)

    return final_handler


def _start_of_layer_download(layer_name):
    TELLAE_STORE.main_dialog.start_progress(f"Téléchargement de la couche '{layer_name}' ...")


def _end_of_layer_download():
    # stop progress bar
    TELLAE_STORE.main_dialog.end_progress()


# layer init context

class LayerInitContext:
    """
    Simple context used for initialising layers classes and catching errors.

    Displays a popup upon error.
    """

    def __init__(self, layer_name, verbose=True):

        self.layer_name = layer_name

        self.verbose = verbose

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # signal error
        if exc_type is not None and self.verbose:
            # TODO: call equivalent of signal_layer_add_error
            log(f"ERROR with {self.layer_name}")

        return True
