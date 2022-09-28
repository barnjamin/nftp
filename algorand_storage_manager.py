import base64
import logging
import stat
import beaker as bkr

from algorand.contract import NFTP
from nftp import StorageManager, FileStat


ALGOD_HOST = "http://localhost:4001"
ALGOD_TOKEN = "a" * 64


class AlgorandStorageManager(StorageManager):
    def __init__(
        self, app_client: bkr.client.ApplicationClient, storage_size: int = 1024
    ):
        self.app_client = app_client
        self.storage_size = storage_size
        super().__init__()

    @staticmethod
    def from_app_id(app_id: int) -> "AlgorandStorageManager":
        # TODO: Cheating
        acct = bkr.sandbox.get_accounts().pop()
        algod_client = bkr.sandbox.clients.get_algod_client()

        return AlgorandStorageManager(
            app_client=bkr.client.application_client.ApplicationClient(
                algod_client, NFTP(), signer=acct.signer, app_id=app_id
            )
        )

    def list_files(self) -> dict[str, FileStat]:
        files: dict[str, FileStat] = {}

        boxes = self.app_client.client.application_boxes(self.app_client.app_id)

        for box in boxes["boxes"]:
            fname, idx = self._box_seq(base64.b64decode(box["name"]))

            if fname not in files or idx > files[fname].num_boxes:
                # Idk about the order of these being guaranteed
                fst = FileStat(idx)
                fst.st_mode = stat.S_IFREG | 0o666
                fst.st_nlink = 1
                fst.st_size = self.storage_size * (idx + 1)
                files[fname] = fst

        return files

    def create_file(self, name: str, mode: int, dev: int):
        self._write_box(name, 0, bytes(self.storage_size))
        self.files = self.list_files()
        # fst = FileStat()
        # fst.st_mode = stat.S_IFREG | 0o666
        # fst.st_nlink = 1
        # fst.st_size = 0
        # self.files[name] = fst

    def read_file(self, name: str, offset: int, size: int) -> bytes:
        # refreshes our list
        self.file_exists(name)

        slen = self.files[name].num_boxes * self.storage_size

        logging.debug(f"read file: {slen}")

        buf = b""
        if offset < slen:
            if offset + size > slen:
                size = slen - offset

            start_idx = offset // self.storage_size
            start_offset = offset % self.storage_size

            stop_idx = size // self.storage_size
            stop_offset = self.storage_size - (size % self.storage_size)

            logging.debug(
                "{} {} {} {}".format(start_idx, start_offset, stop_idx, stop_offset)
            )
            for idx in range(start_idx, stop_idx):
                buf += self._read_box(name, idx)[start_offset:stop_offset]
        else:
            buf = bytes(size)

        return buf

    def write_file(self, name: str, offset: int, buf: bytes):
        start_idx = offset // self.storage_size
        start_offset = offset % self.storage_size

        stop_idx = (offset + len(buf)) // self.storage_size
        stop_offset = (offset + len(buf)) % self.storage_size

        logging.debug(
            f"writing from {start_idx} : {start_offset} to {stop_idx} : {stop_offset}"
        )
        for idx in range(start_idx, stop_idx + 1):
            working_buf = bytearray(
                buf[idx * self.storage_size : (idx + 1) * self.storage_size]
            )
            if idx == start_idx and start_offset > 0:
                # Partial write, might as well read the whole storage unit
                working_buf[:start_idx] = self._read_box(name, idx)[start_idx:]
            elif idx == stop_idx and stop_offset > 0:
                working_buf[stop_idx:] = self._read_box(name, idx)[:stop_idx]

            if len(working_buf) == 0:
                return

            logging.debug(f"about to write: {working_buf.hex()}")
            try:
                self._write_box(name, idx, working_buf)
            except Exception as e:
                logging.error(f"Failed to write: {e}")
                raise e

    def delete_file(self, name: str):
        # refresh cache
        self.file_exists(name)
        for idx in range(self.files[name].num_boxes + 1):
            self._delete_box(name, idx)

        del self.files[name]

    def _read_box(self, name: str, idx: int) -> bytes:
        logging.debug(f"_read_box: {name} {idx}")
        box_name = self._box_name(name, idx)
        logging.debug(f"getting app box: {name} {idx}")
        try:
            box_response = self.app_client.client.application_box_by_name(
                self.app_client.app_id, box_name
            )
            return base64.b64decode(box_response["value"])
        except Exception as e:
            logging.error(f"Failed to get box: {e}")
            raise e

    def _delete_box(self, name: bytes, idx: int):
        box_name = self._box_name(name, idx)
        self.app_client.call(
            NFTP.delete_data,
            box_name=box_name,
            boxes=[[self.app_client.app_id, box_name]],
        )

    def _write_box(self, name: bytes, idx: int, data: bytes):
        box_name = self._box_name(name, idx)
        logging.debug(f"writing to {box_name.hex()} ({len(data)} bytes)")
        try:
            self.app_client.call(
                NFTP.put_data,
                box_name=box_name,
                data=data,
                boxes=[[self.app_client.app_id, box_name]],
            )
        except Exception as e:
            logging.error(f"Failed to write in app call: {e}")
            raise e

    def _box_name(self, name: str, idx: int) -> bytes:
        return name.encode() + idx.to_bytes(4, "big")

    def _box_seq(self, box_name: bytes) -> tuple[str, int]:
        fname = box_name[:-4].decode("utf-8")
        idx = int.from_bytes(box_name[-4:], "big")
        return [fname, idx]
