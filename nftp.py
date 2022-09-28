from abc import ABC, abstractmethod
import logging
import stat, errno
import beaker as bkr
from algorand_storage_manager import AlgorandStorageManager

import fuse
from fuse import Fuse


fuse.fuse_python_api = (0, 2)

logging.basicConfig(filename="/tmp/nftpfs.log", filemode="w", level=logging.DEBUG)


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


class StorageManager(ABC):
    def __init__(self):
        self.files: dict[str, FileStat] = self.list_files()

    def filenames(self) -> list[str]:
        return list(self.files.keys())

    def exists(self, name: str) -> bool:
        # refresh cache
        self.files = self.list_files()
        return name in self.files

    def file_stat(self, name: str):
        # reuse cached, this is called a lot
        # will raise key error, thats ok
        return self.files[name]

    @abstractmethod
    def list_files(self) -> dict[str, FileStat]:
        ...

    @abstractmethod
    def read_file(self, name: str, offset: int, size: int) -> bytes:
        ...

    @abstractmethod
    def write_file(self, name: str, offset: int, buf: int):
        ...

    @abstractmethod
    def delete(self, name: str):
        ...


class NftpFS(Fuse):
    def __init__(self, storage_manager: StorageManager, **kwargs):
        super().__init__(**kwargs)
        self.storage_manager = storage_manager

        logging.debug(self.storage_manager.filenames())

    def getattr(self, path: str):
        logging.debug(f"getattr for {path}")

        if path == "/":
            fst = FileStat(0)
            fst.st_mode = stat.S_IFDIR | 0o755
            fst.st_nlink = 2
            return fst

        if self.storage_manager.exists(path[1:]):
            logging.debug("file exists, getting stats")
            try:
                fst = self.storage_manager.file_stat(path[1:])
            except Exception as e:
                logging.error("getattr exception: " + e.__str__())
            return fst
        else:
            return -errno.ENOENT

    def readdir(self, path: bytes, offset: int):
        logging.debug(f"readdir: {path} {offset}")

        try:
            fnames = self.storage_manager.filenames()
        except Exception as e:
            logging.error("readdir error:" + e.__str__())

        for fname in [".", ".."] + fnames:
            yield fuse.Direntry(fname)

    def open(self, path: str, flags: int):
        # TODO: check if allowed?
        logging.debug(f"open: {path}")

        try:
            ok = self.storage_manager.exists(path[1:])
        except Exception as e:
            logging.error("open error: " + e.__str__())

        return int(not ok)

    def read(self, path: str, size: int, offset: int) -> bytes:
        logging.debug(f"read: {path}")
        try:
            buf = self.storage_manager.read_file(path[1:], offset, size)
        except Exception as e:
            logging.error("read error: " + e.__str__())

        return buf

    def write(self, path: str, buf: int, offset: int) -> int:
        logging.debug(f"write: {path}")

        try:
            written = self.storage_manager.write_file(path[1:], offset, buf)
        except Exception as e:
            logging.error("write error: " + e.__str__())

        return written

    def unlink(self, path: str):
        logging.debug(f"unlink: {path}")
        try:

            self.storage_manager.delete(path[1:])
        except Exception as e:
            logging.error("unlink error: " + e.__str__())


def main():
    ALGORAND_APP_ID = 125
    server = NftpFS(
        storage_manager=AlgorandStorageManager(ALGORAND_APP_ID),
        version="%prog " + fuse.__version__,
        usage=""" Userspace hello example """ + Fuse.fusage,
        dash_s_do="setsingle",
    )

    server.parse(errex=1)
    server.main()


if __name__ == "__main__":
    main()
