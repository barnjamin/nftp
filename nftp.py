import base64
from genericpath import exists
import os, stat, errno
import algosdk
from algosdk.v2client.algod import AlgodClient
import beaker as bkr
from contract import NFTP

import fuse
from fuse import Fuse

APP_ID = (125,)
ALGOD_HOST = ("http://localhost:4001",)
ALGOD_TOKEN = ("a" * 64,)

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
        return self.files.keys()

    def list_files(self) -> dict[str, FileStat]:
        files: dict[str, FileStat] = {}

        boxes = self.app_client.client.application_boxes(self.app_client.app_id)
        for box in boxes["boxes"]:
            name = base64.b64decode(box["name"])
            # 4 bytes for uint32
            fname = name[:-4].decode("utf-8")
            idx = int.from_bytes(name[-4:], "big")

            if fname not in self.files or idx > self.files[fname]:
                files[fname] = FileStat(idx)
        return files

    def read_file(self, name: bytes, offset: int, len: int) -> bytes:
        # refresh our list
        self.files = self.list_files()
        if name not in self.files:
            raise Exception(-errno.ENOENT)

        slen = self.files[name].num_boxes * self.storage_size

        buf = b""
        if offset < slen:
            if offset + size > slen:
                size = slen - offset

            start_idx = offset // self.storage_size
            start_offset = offset % self.storage_size

            stop_idx = size // self.storage_size
            stop_offset = size % self.storage_size

            for chunk in range(start_idx, stop_idx):
                buf += self._read_box(name, start_idx + chunk)

            buf = buf[start_offset:stop_offset]
        else:
            buf = bytes(size)

        return buf

    def write_file(self, name: str, offset: int, buf: int):
        start_idx = offset // self.storage_size
        start_offset = offset % self.storage_size

        stop_idx = (offset + len(buf)) // self.storage_size
        stop_offset = offset % self.storage_size

        for idx in range(start_idx, stop_idx + 1):
            working_buff = bytes(self.storage_size)
            if stop_offset > 0 or start_offset > 0:
                # Partial write, might as well read the whole storage unit
                working_buff[:] = self._read_box(name, idx)

            working_buff[start_offset:stop_offset] = buf[
                idx * self.storage_size : (idx + 1) * self.storage_size
            ]

            self._write_box(name, idx, working_buff)

    def delete(self, name: str):
        # refresh index
        self.files = self.list_files()

        for idx in range(self.files[name].num_boxes + 1):
            self._delete_box(name, idx)

    def exists(self, name: str) -> bool:
        # refresh cache
        self.files = self.list_files()
        return name in self.files

    def file_stat(self, name: str):
        # use cached
        # will raise key error, thats ok
        return self.files[name]

    def _read_box(self, name: bytes, idx: int) -> bytes:
        box_name = self._box_name(name, idx)
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

    def _box_name(self, name: str, idx: int):
        return f"{name.encode()}{idx.to_bytes(4, 'big')}"

    def _box_seq(self, box_name: bytes) -> tuple[str, int]:
        fname = box_name[:-4].decode("utf-8")
        idx = int.from_bytes(box_name[-4:], "big")
        return [fname, idx]


class HelloFS(Fuse):
    def __init__(self, storage_manager: StorageManager, **kwargs):
        super().__init__(**kwargs)
        self.storage_manager = storage_manager

    def getattr(self, path):
        if path == "/":
            fst = FileStat()
            fst.st_mode = stat.S_IFDIR | 0o755
            fst.st_nlink = 2

        return self.storage_manager.file_stat(path[1:])

    def readdir(self, path, offset):
        for r in [".", ".."] + list(self.storage_manager.filenames()):
            yield fuse.Direntry(r)

    def open(self, path, flags):
        return int(self.storage_manager.exists(path[1:]))

    def read(self, path, size, offset) -> bytes:
        return self.storage_manager.read_file(path[1:], offset, size)

    def write(self, path: str, buf: int, offset: int) -> int:
        return self.storage_manager.write_file(path[1:], offset, buf)

    def unlink(self, path: str):
        return int(self.storage_manager.delete(path[1:]))

    def mkdir(self, path, mode):
        return 0

    def rmdir(self, path):
        return 0


def main():
    usage = """ Userspace hello example """ + Fuse.fusage
    server = HelloFS(
        version="%prog " + fuse.__version__,
        usage=usage,
        dash_s_do="setsingle",
    )

    server.parse(errex=1)
    server.main()


if __name__ == "__main__":
    main()
