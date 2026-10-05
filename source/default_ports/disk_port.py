
from source.utils import get_safe_path, sanitize_path, find_files
from source.port_interface import PortInterface

import os

FILE_ERR = 0x01
CRIT_FILE_ERR = 0x02
SEARCH_ERR = 0x03

OPEN_BUSY = 0x01
CLOSE_BUSY = 0x02
FNF_ERR = 0x03
DIR_ERR = 0x04
PERM_ERR = 0x05

HARDWARE_DISCONNECT = 0x01

SEARCH_FAIL = 0x01
SEEK_FAIL = 0x02


class DiskPort:
    def __init__(self, folder_name):
        self.wrapper = None
        self.is_ticking = True

        self._curr_file_name = ""
        self._file_name_offset = 0
        self._files = []
        self._file_index = 0
        self.busy = False

        self.stream_max = 32

        self._file = None
        self._path = get_safe_path(folder_name)

        self._delay = 0

    def status(self):
        status = 0x00
        if self.busy:
            status |= 0x01
        if self._file:
            status |= 0x02
        if self._is_at_eof():
            status |= 0x40
        return status

    def command(self, cmd):
        match cmd:
            case 1:   # SEARCH
                try:
                    self._files = find_files(self._path, self._curr_file_name)
                except OSError:
                    self.wrapper.err(SEARCH_ERR, SEARCH_FAIL)
                self.wrapper.set_arg(len(self._files))
            case 2:   # RSEEK
                self._file_index = self.wrapper.arg()
                if self._file_index < len(self._files):
                    self._curr_file_name = self._files[self._file_index]
                    self._file_name_offset = 0
                    self.wrapper.begin_stream(PortInterface.STREAM_STR_OUT)
                else:
                    self.wrapper.err(SEARCH_ERR, SEEK_FAIL)
            case 3:   # NAME
                self.wrapper.begin_stream(PortInterface.STREAM_STR_IN)
            case 4:   # OPEN
                file_mode = self._get_file_mode(self.wrapper.argl)
                self._open_file(file_mode)
            case 5:   # CLOSE
                self._close_file()
            case 6:   # READ
                self.wrapper.begin_stream(PortInterface.STREAM_DATA_OUT)
            case _:
                pass

    def reset(self):
        self._close_file()
        self.busy = False
        self._curr_file_name = ""
        self._file_name_offset = 0
        self._mode = 0x01 

    def ack_err(self):
        self.busy = False

    def stream_string(self, string):
        self._curr_file_name = string

    def stream_str_next(self):
        if self._file_name_offset >= len(self._curr_file_name):
            return 0
        char = self._curr_file_name[self._file_name_offset]
        self._file_name_offset += 1
        return ord(char)

    def stream_next(self):
        if not self._file:
            self.wrapper.err(0x00)   # Placeholder
            return 0x00
        byte = self._file.read(1)
        if not byte:
            return 0x00
        return byte[0]

    def tick(self):
        if self._delay > 0:
            self._delay -= 1

    def _close_file(self):
        if self.busy:
            self.wrapper.err(FILE_ERR, CLOSE_BUSY)
        if self._file:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None

    def _open_file(self, mode):
        if self.busy:
            self.wrapper.err(FILE_ERR, OPEN_BUSY)

        self._close_file()

        file_path = sanitize_path(self._path, self._curr_file_name)
        try:
            self._file = open(file_path, mode)
        except FileNotFoundError:
            self.wrapper.err(FILE_ERR, FNF_ERR)
        except IsADirectoryError:
            self.wrapper.err(FILE_ERR, DIR_ERR)
        except PermissionError:
            self.wrapper.err(FILE_ERR, PERM_ERR)
        except (BlockingIOError, InterruptedError):
            self.wrapper.err(CRIT_FILE_ERR)
        except (BrokenPipeError):
            self.wrapper.err(CRIT_FILE_ERR, HARDWARE_DISCONNECT)
        except OSError:
            self.wrapper.err(FILE_ERR, 0xFF)

    def _is_at_eof(self):
        if not self._file:
            return True

        current_pos = self._file.tell()
        file_size = os.fstat(self._file.fileno()).st_size
        return current_pos >= file_size

    def _get_file_mode(self, mode):
        mode = mode & 0x3
        match mode:
            case 0x0:
                return "rb"
            case 0x1:
                return "rb+"
            case 0x2:
                return "wb+"
            case 0x3:
                return "ab"

    def dma_read_ready(self):
        return self._delay <= 0

    def dma_read(self):
        return self.stream_next()

    def dma_end(self):
        return self.wrapper._err_mask != 0 or self._is_at_eof()
