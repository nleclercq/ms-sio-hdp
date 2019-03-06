#-----------------------------------------------------------------------------------------------
# NotebookCellContent: attach logging to a specifc notebook cell   
# This code comes from a 2017 Synchrontron SOLEIL projedct dev. by Nicolas Leclercq
#-----------------------------------------------------------------------------------------------

import sys
import logging
import traceback
from uuid import uuid4
from IPython import get_ipython
from IPython.display import display, clear_output

#-----------------------------------------------------------------------------------------------
# CellOutput
#-----------------------------------------------------------------------------------------------
class CellOutput(object):
    def __init__(self):
        k = get_ipython().kernel
        self._ident = k._parent_ident
        self._header = k._parent_header
        self._save_context = None

    def __enter__(self):
        kernel = get_ipython().kernel
        self._save_context = (kernel._parent_ident, kernel._parent_header)
        sys.stdout.flush()
        sys.stderr.flush()
        kernel.set_parent(self._ident, self._header)

    def __exit__(self, etype, evalue, tb):
        sys.stdout.flush()
        sys.stderr.flush()
        kernel = get_ipython().kernel
        kernel.set_parent(*self._save_context)
        return False

    def clear_output(self):
        with self:
            clear_output()

    def close(self):
        pass
        
#-----------------------------------------------------------------------------------------------
# NotebookCellContent
#-----------------------------------------------------------------------------------------------
class NotebookCellContent(object):
    default_logger = "api-transilien"

    def __init__(self, name=None, logger=None, output=None):
        uuid = uuid4().hex
        self._uid = uuid
        self._name = name if name is not None else str(uuid)
        self._output = CellOutput() if output is None else output
        self._logger = logger if logger else logging.getLogger(NotebookCellContent.default_logger)

    @property
    def name(self):
        return self._name

    @property
    def uid(self):
        return self._uid
        
    @property
    def logger(self):
        return self._logger

    @logger.setter
    def logger(self, l):
        self._logger = l

    @property
    def output(self):
        return self._output

    @output.setter
    def output(self, output):
        self._output = output
        
    def display(self, widgets):
        with self._output:
            display(widgets)

    def clear_output(self):
        self._output.clear_output()

    def close_output(self):
        self._output.close()
        
    def set_logging_level(self, level):
        self._logger.setLevel(level)

    def print_to_cell(self, *args):
        self.print(*args)

    def print(self, *args, **kwargs):
        with self._output:
            try:
                self._logger.print(*args, **kwargs)
            except:
                print(*args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        with self._output:
            self._logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        with self._output:
            self._logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        with self._output:
            self._logger.warning(msg, *args, **kwargs)

    def print_error(self, msg, *args, **kwargs):
        with self._output:
            self._logger.error(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        with self._output:
            self._logger.error(msg, *args, **kwargs)
            exc_info = sys.exc_info()
            traceback.print_exception(*exc_info)
            del exc_info

    def critical(self, msg, *args, **kwargs):
        with self._output:
            self._logger.critical(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)