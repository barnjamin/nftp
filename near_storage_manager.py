import base64
from typing import cast
import logging
import stat

from nftp import StorageManager, FileStat

class NearStorageManager(StorageManager):
    def __init__(
        self,  storage_size: int = 1024
    ):
        self.storage_size = storage_size
        super().__init__()

    @staticmethod
    def factory(args) -> "NearStorageManager":
        return NearStorageManager()

    def list_files(self) -> dict[str, FileStat]:
        logging.info(f"{app_state}")

        files: dict[str, FileStat] = {}

#        for fname, num_boxes in app_state.items():
#            fname = self.strip_leading_zeros(fname).decode("utf-8")
#            if fname not in files or num_boxes > files[fname].num_boxes:
#                # Idk about the order of these being guaranteed
#                fst = FileStat(num_boxes)
#                fst.st_mode = stat.S_IFREG | 0o666
#                fst.st_nlink = 1
#                fst.st_size = self.storage_size * num_boxes
#                files[fname] = fst

        return files

    def strip_leading_zeros(self, name: bytes) -> bytes:
        for idx, b in enumerate(name):
            if b != 0:
                return name[idx:]
        return b""

    def create_file(self, name: str, mode: int, dev: int):
#        self._create_acct(name, 0)
#        self.files = self.list_files()
        logging.debug(f"{self.files}")

    def read_file(self, name: str, offset: int, size: int) -> bytes:
        # refreshes our list
#        self.file_exists(name)

#        slen = self.files[name].num_boxes * self.storage_size

        logging.debug(f"read file: {slen}")

        buf = b""
#        if offset < slen:
#            if offset + size > slen:
#                size = slen - offset
#
#            start_idx = offset // self.storage_size
#            start_offset = offset % self.storage_size
#
#            stop_idx = size // self.storage_size
#            stop_offset = self.storage_size - (size % self.storage_size)
#
#            logging.debug(
#                "{} {} {} {}".format(start_idx, start_offset, stop_idx, stop_offset)
#            )
#            for idx in range(start_idx, stop_idx):
#                buf += self._read_acct(name, idx)[start_offset:stop_offset]
#
#            buf = buf.strip(bytes(1))
#            logging.debug(f"{buf.hex()}")
#
#        else:
#            buf = bytes(size)

        return buf

    def write_file(self, name: str, offset: int, buf: bytes):
        start_idx = offset // self.storage_size
        start_offset = offset % self.storage_size

        stop_idx = (offset + len(buf)) // self.storage_size
        stop_offset = (offset + len(buf)) % self.storage_size

        logging.debug(
            f"writing {len(buf)} bytes from {start_idx} : {start_offset} to {stop_idx} : {stop_offset}"
        )
#        for idx in range(stop_idx - start_idx):
#            box_idx = start_idx + idx
#            if box_idx >= self.files[name].num_boxes:
#                self._create_acct(name, box_idx)
#                self.files = self.list_files()
#
#            try:
#                logging.debug(f"{buf.hex()}")
#                working_buf = bytearray(
#                    buf[idx * self.storage_size : (idx + 1) * self.storage_size]
#                )
#                logging.debug(f"working buf size: {len(working_buf)}")
#                if box_idx == start_idx and start_offset > 0:
#                    # Partial write, might as well read the whole storage unit
#                    working_buf[:start_offset] = self._read_acct(name, box_idx)[
#                        start_offset:
#                    ]
#                elif box_idx == stop_idx and stop_offset > 0:
#                    working_buf[stop_offset:] = self._read_acct(name, box_idx)[
#                        :stop_offset
#                    ]
#
#                if len(working_buf) == 0:
#                    return 0
#
#                logging.debug(f"about to write: {working_buf.hex()}")
#                self._write_acct(name, box_idx, working_buf)
#            except Exception as e:
#                logging.error(f"Failed to write: {e}")
#                raise e
        return len(buf)

    def delete_file(self, name: str):
        # refresh cache
#        self.file_exists(name)
#        for idx in range(self.files[name].num_boxes + 1):
#            self._delete_acct(name, idx)
#        del self.files[name]
        pass

