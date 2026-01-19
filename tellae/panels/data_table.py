from qgis.PyQt.QtWidgets import QPushButton, QTableWidgetItem, QTableWidget
from PyQt5.QtWidgets import QStyle


class DataTable:

    def __init__(self, parent_panel, table_widget):

        self.parent_panel = parent_panel

        self.table_widget = table_widget

        # total table length is 791, scroll bar is 16 => header width must total to 775
        self._headers = None

        # disable table edition
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)

    @property
    def headers(self):
        return self._headers

    def set_headers(self, headers):

        self._headers = headers

        # set number of columns
        self.table_widget.setColumnCount(len(self._headers))

        # populate headers
        self.table_widget.setHorizontalHeaderLabels([header["text"] for header in self._headers])
        for col, header in enumerate(self._headers):
            if "width" in header:
                self.table_widget.setColumnWidth(col, header["width"])

    def fill_table_with_items(self, items):

        # set number of rows and columns
        self.table_widget.setRowCount(len(items))

        # populate table cells
        for row, layer in enumerate(items):
            for col, header in enumerate(self._headers):
                # evaluate its content depending on the row and column
                if "slot" in header:
                    header["slot"](self.table_widget, row, col, layer, header)
                    continue
                elif callable(header["value"]):
                    text = header["value"](layer)
                else:
                    text = layer[header["value"]]

                # create a table cell
                cell = QTableWidgetItem(text)

                # set cell text and tooltip
                # cell.setText(text)
                cell.setToolTip(text)

                # set text alignment
                if "align" in header:
                    cell.setTextAlignment(header["align"])

                # put the cell in the table
                self.table_widget.setItem(row, col, cell)

    def table_button_slot(self, handler, icon="SP_DialogSaveButton"):

        def button_maker(table_widget, row_ix, col_ix, _, __):
            btn = QPushButton(table_widget)
            btn.setIcon(self.parent_panel.dlg.style().standardIcon(getattr(QStyle, icon)))
            btn.clicked.connect(lambda state, x=row_ix: handler(x))
            table_widget.setCellWidget(row_ix, col_ix, btn)

        return button_maker
