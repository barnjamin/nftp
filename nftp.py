from abc import ABC, abstractmethod
import logging
import stat, errno
import fuse
from fuse import Fuse

fuse.fuse_python_api = (0, 2)


class FileStat(fuse.Stat):
    """data structure returned from stat requests on files"""

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
    """abstracts blockchain specific access to allow consistent api across chains"""

    def __init__(self):
        self.files: dict[str, FileStat] = self.list_files()

    def file_names(self) -> list[str]:
        return list(self.files.keys())

    def file_exists(self, name: str) -> bool:
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
    def create_file(self, name: str):
        ...

    @abstractmethod
    def read_file(self, name: str, offset: int, size: int) -> bytes:
        ...

    @abstractmethod
    def write_file(self, name: str, offset: int, buf: int):
        ...

    @abstractmethod
    def delete_file(self, name: str):
        ...


class NftpFS(Fuse):
    """Nakamoto File Transfer Protocol

    enable the free (not actually free) sharing of data using simple (complicated)
    memory management through on chain and cross chain operations

    """

    def __init__(self, storage_manager: StorageManager, **kwargs):
        super().__init__(**kwargs)
        self.storage_manager = storage_manager
        logging.debug(
            f"initialized with filenames: {self.storage_manager.file_names()}"
        )

    def getattr(self, path: str):
        logging.debug(f"getattr for {path}")

        if path == "/":
            fst = FileStat(0)
            fst.st_mode = stat.S_IFDIR | 0o755
            fst.st_nlink = 2
            return fst

        if self.storage_manager.file_exists(path[1:]):
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
            fnames = self.storage_manager.file_names()
        except Exception as e:
            logging.error("readdir error:" + e.__str__())

        for fname in [".", ".."] + fnames:
            yield fuse.Direntry(fname)

    def open(self, path: str, flags: int):
        # TODO: check if allowed based on file perms?
        logging.debug(f"open: {path}")

        try:
            ok = self.storage_manager.file_exists(path[1:])
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

    def mknod(self, path, mode, dev):
        logging.debug(f"mknod: {path} {mode} {dev}, {type(mode)}, {type(dev)}")
        self.storage_manager.create_file(path[1:], mode, dev)

    def unlink(self, path):
        logging.debug(f"unlink: {path}")
        self.storage_manager.delete_file(path[1:])

    def readlink(self, path):
        logging.debug(f"readlink: {path}")
        return
        # return os.readlink("." + path)

    def copy_file_range(self):
        logging.debug(f"copy file range")

    def rmdir(self, path):
        logging.debug(f"readlink: {path}")
        # os.rmdir("." + path)
        return

    def symlink(self, path, path1):
        logging.debug(f"symlink: {path1, path}")
        return 0

    def rename(self, path, path1):
        logging.debug(f"rename: {path1, path}")
        return 0

    def link(self, path, path1):
        logging.debug(f"link: {path1, path}")
        return 0

    def chmod(self, path, mode):
        logging.debug(f"chmod: {path, mode}")
        return 0

    def chown(self, path, user, group):
        logging.debug(f"chown: {path, user, group}")
        return 0

    def truncate(self, path, len):
        logging.debug(f"truncate: {path, len}")
        # f = open("." + path, "a")
        # f.truncate(len)
        # f.close()

        # TODO:
        return 0

    def close(self):
        logging.debug("close")

    def mkdir(self, path, mode):
        logging.debug(f"mkdir: {path, mode}")
        # os.mkdir("." + path, mode)

    def utime(self, path, times):
        logging.debug(f"utime: {path, times}")

    # def release(self):
    #    logging.debug("release")
    # def statfs(self):
    #    logging.debug("statfs")
    # def fsync(self):
    #    logging.debug("fsync")
    # def create(self):
    #    logging.debug("create")
    # def opendir(self):
    #    logging.debug("opendir")
    # def releasedir(self):
    #    logging.debug("releasedir")
    # def fsyncdir(self):
    #    logging.debug("fsyncdir")
    # def flush(self):
    #    logging.debug("flushdir")
    # def fgetattr(self):
    #    logging.debug("fgetattr")
    # def ftruncate(self):
    #    logging.debug("ftruncate")
    # def getxattr(self):
    #    logging.debug("getxattr")
    # def listxattr(self):
    #    logging.debug("listxattr")
    # def setxattr(self):
    #    logging.debug("setxattr")
    # def removexattr(self):
    #    logging.debug("removexattr")
    # def access(self):
    #    logging.debug("access")
    # def lock(self):
    #    logging.debug("lock")
    # def utimens(self):
    #    logging.debug("utimens")
    # def bmap(self):
    #    logging.debug("bmap")
    # def fsdestroy(self):
    #    logging.debug("fsdestroy")
    # def ioctl(self):
    #    logging.debug("ioctl")
    # def poll(self):
    #    logging.debug("poll")
