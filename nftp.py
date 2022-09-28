import base64
import logging
import os, stat, errno
from algosdk.v2client.algod import AlgodClient
import beaker as bkr
from contract import NFTP

import fuse
from fuse import Fuse

APP_ID = 125
ALGOD_HOST = "http://localhost:4001"
ALGOD_TOKEN = "a" * 64

fuse.fuse_python_api = (0, 2)


class FileStat(fuse.Stat):
    def __init__(self, num_boxes: int):
        self.num_boxes = num_boxes

        # permissions
        self.st_mode = 0
        # ??
        self.st_ino = 0
        # device id holding file
        self.st_dev = 0
        # number of links
        self.st_nlink = 0
        # user id of file owner
        self.st_uid = 0
        # group id of file
        self.st_gid = 0
        # size of file
        self.st_size = 0
        # access time
        self.st_atime = 0
        # mod time
        self.st_mtime = 0
        # change time
        self.st_ctime = 0


class StorageManager:
    def __init__(self, app_client: bkr.client.ApplicationClient, storage_size: int):
        self.app_client = app_client
        self.storage_size = storage_size
        self.files: dict[str, FileStat] = self.list_files()

    def filenames(self) -> list[str]:
        return list(self.files.keys())

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
                fst.st_size = self.storage_size * idx
                files[fname] = fst

        return files

    def read_file(self, name: str, offset: int, size: int) -> bytes:
        # refreshes our list
        self.exists(name)

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

    def write_file(self, name: str, offset: int, buf: int):
        # TODO: refresh the cache?
        # create account if new?
        start_idx = offset // self.storage_size
        start_offset = offset % self.storage_size

        stop_idx = (offset + len(buf)) // self.storage_size
        stop_offset = offset % self.storage_size

        for idx in range(start_idx, stop_idx + 1):
            working_buf = bytes(self.storage_size)
            if stop_offset > 0 or start_offset > 0:
                # Partial write, might as well read the whole storage unit
                working_buf[:] = self._read_box(name, idx)

            working_buf[start_offset:stop_offset] = buf[
                idx * self.storage_size : (idx + 1) * self.storage_size
            ]

            self._write_box(name, idx, working_buf)

    def delete(self, name: str):
        # refresh cache
        self.exists(name)
        for idx in range(self.files[name].num_boxes + 1):
            self._delete_box(name, idx)

    def exists(self, name: str) -> bool:
        # refresh cache
        self.files = self.list_files()
        return name in self.files

    def file_stat(self, name: str):
        # reuse cached, this is called a lot
        # will raise key error, thats ok
        return self.files[name]

    def _read_box(self, name: str, idx: int) -> bytes:
        logging.debug(f"_read_box: {name} {idx}")
        box_name = self._box_name(name, idx)
        logging.debug(f"getting app box: {name} {idx}")
        box_response = self.app_client.client.application_box_by_name(
            self.app_client.app_id, box_name
        )
        return base64.b64decode(box_response["value"])

    def _delete_box(self, name: bytes, idx: int):
        box_name = self._box_name(name, idx)
        self.app_client.call(NFTP.delete_data, box_name=box_name)

    def _write_box(self, name: bytes, idx: int, data: bytes):
        box_name = self._box_name(name, idx)
        self.app_client.call(NFTP.put_data, box_name=box_name, data=data)

    def _box_name(self, name: str, idx: int) -> bytes:
        return name.encode() + idx.to_bytes(4, "big")

    def _box_seq(self, box_name: bytes) -> tuple[str, int]:
        fname = box_name[:-4].decode("utf-8")
        idx = int.from_bytes(box_name[-4:], "big")
        return [fname, idx]


class HelloFS(Fuse):
    def __init__(self, storage_manager: StorageManager, **kwargs):
        super().__init__(**kwargs)
        self.storage_manager = storage_manager

        logging.basicConfig(filename="/tmp/003.log", filemode="w", level=logging.DEBUG)
        logging.debug(self.storage_manager.filenames())

    def getattr(self, path: str):
        logging.debug("getting attr: " + str(type(path)))
        if path == "/":
            logging.debug("path is /")
            fst = FileStat(0)
            fst.st_mode = stat.S_IFDIR | 0o755
            fst.st_nlink = 2
            return fst

        logging.debug(f"path is something else")
        if self.storage_manager.exists(path[1:]):
            logging.debug("Exists??")
            try:
                fst = self.storage_manager.file_stat(path[1:])
            except Exception as e:
                logging.error("getattr" + e.__str__())
            return fst
        else:
            return -errno.ENOENT

    def readdir(self, path: bytes, offset: int):
        logging.debug("readdir: ")
        try:
            logging.debug("getting filenames")
            fnames = self.storage_manager.filenames()
        except Exception as e:
            logging.error("readdir" + e.__str__())

        for fname in [".", ".."] + fnames:
            yield fuse.Direntry(fname)

    def open(self, path: str, flags: int):
        # TODO: check if allowed?
        logging.debug("open: " + str(type(path)))
        try:
            ok = self.storage_manager.exists(path[1:])
        except Exception as e:
            logging.error("open" + e.__str__())
        return int(not ok)

    def read(self, path: str, size: int, offset: int) -> bytes:
        logging.debug("read: " + str(type(path)))
        try:
            buf = self.storage_manager.read_file(path[1:], offset, size)
        except Exception as e:
            logging.error("read" + e.__str__())

        return buf

    def write(self, path: str, buf: int, offset: int) -> int:
        logging.debug("write: " + str(type(path)))
        try:
            written = self.storage_manager.write_file(path[1:], offset, buf)
        except Exception as e:
            logging.error("write" + e.__str__())
        return written

    def unlink(self, path: str):
        self.storage_manager.delete(path[1:])


def main():
    usage = """ Userspace hello example """ + Fuse.fusage

    acct = bkr.sandbox.get_accounts().pop()
    algod_client = bkr.sandbox.clients.get_algod_client()
    app_client = bkr.client.application_client.ApplicationClient(
        client=algod_client, app=NFTP(), signer=acct.signer, app_id=APP_ID
    )

    server = HelloFS(
        storage_manager=StorageManager(app_client, 1024),
        version="%prog " + fuse.__version__,
        usage=usage,
        dash_s_do="setsingle",
    )

    server.parse(errex=1)
    server.main()


if __name__ == "__main__":
    main()
