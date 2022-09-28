#!/usr/bin/env python

#  sudo dnf install fuse-devel
#  python3 -m pip install fuse-python
#  python3 nftp.py  ~/mnt
# .
# .
# .
# fusermount3 -u ~/mnt

from __future__ import print_function

import os, sys
from errno import *
from stat import *
import fcntl
from threading import Lock

# pull in some spaghetti to make this stuff work without fuse-py being installed
try:
    import _find_fuse_parts
except ImportError:
    pass
import fuse
from fuse import Fuse

import logging

if not hasattr(fuse, "__version__"):
    raise RuntimeError(
        "your fuse-py doesn't know of fuse.__version__, probably it's too old."
    )

fuse.fuse_python_api = (0, 2)

fuse.feature_assert("stateful_files", "has_init")

logger = logging.getLogger("spam_application")
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler("/home/jsiegel/spam.log")
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)


def flag2mode(flags):
    md = {os.O_RDONLY: "rb", os.O_WRONLY: "wb", os.O_RDWR: "wb+"}
    m = md[flags & (os.O_RDONLY | os.O_WRONLY | os.O_RDWR)]

    if flags | os.O_APPEND:
        m = m.replace("w", "a", 1)

    return m


class Xmp(Fuse):
    def __init__(self, *args, **kw):
        Fuse.__init__(self, *args, **kw)
        self.root = "/"

    def getattr(self, path):
        logger.info(["getattr", path])
        return os.lstat("." + path)

    def readlink(self, path):
        logger.info("readlink")
        return os.readlink("." + path)

    def readdir(self, path, offset):
        logger.info(["readdir", path, offset])
        for e in os.listdir("." + path):
            yield fuse.Direntry(e)

    def unlink(self, path):
        logger.info("unlink")
        os.unlink("." + path)

    def rmdir(self, path):
        logger.info("rmdir")
        os.rmdir("." + path)

    def symlink(self, path, path1):
        logger.info("symlink")
        os.symlink(path, "." + path1)

    def rename(self, path, path1):
        logger.info("rename")
        os.rename("." + path, "." + path1)

    def link(self, path, path1):
        logger.info("link")
        os.link("." + path, "." + path1)

    def chmod(self, path, mode):
        logger.info("chmod")
        os.chmod("." + path, mode)

    def chown(self, path, user, group):
        logger.info("chown")
        os.chown("." + path, user, group)

    def truncate(self, path, len):
        logger.info("truncate")
        f = open("." + path, "a")
        f.truncate(len)
        f.close()

    def mknod(self, path, mode, dev):
        logger.info("mknod")
        os.mknod("." + path, mode, dev)

    def mkdir(self, path, mode):
        logger.info("mkdir")
        os.mkdir("." + path, mode)

    def utime(self, path, times):
        logger.info("utime")
        os.utime("." + path, times)

    def access(self, path, mode):
        logger.info(["access", path, mode])
        if not os.access("." + path, mode):
            return -EACCES

    def statfs(self):
        """
        Should return an object with statvfs attributes (f_bsize, f_frsize...).
        Eg., the return value of os.statvfs() is such a thing (since py 2.2).
        If you are not reusing an existing statvfs object, start with
        fuse.StatVFS(), and define the attributes.

        To provide usable information (ie., you want sensible df(1)
        output, you are suggested to specify the following attributes:

            - f_bsize - preferred size of file blocks, in bytes
            - f_frsize - fundamental size of file blcoks, in bytes
                [if you have no idea, use the same as blocksize]
            - f_blocks - total number of blocks in the filesystem
            - f_bfree - number of free blocks
            - f_files - total number of file inodes
            - f_ffree - nunber of free file inodes
        """

        logger.info("statfs")
        return os.statvfs(".")

    def fsinit(self):
        os.chdir(self.root)

    class XmpFile(object):
        def __init__(self, path, flags, *mode):
            logger.info(["XmpFile__init__", path, flags, *mode])
            self.file = os.fdopen(os.open("." + path, flags, *mode), flag2mode(flags))
            self.fd = self.file.fileno()
            if hasattr(os, "pread"):
                self.iolock = None
            else:
                self.iolock = Lock()

        def read(self, length, offset):
            logger.info(["XmpFileRead", length, offset])

            if self.iolock:
                self.iolock.acquire()
                try:
                    self.file.seek(offset)
                    return self.file.read(length)
                finally:
                    self.iolock.release()
            else:
                return os.pread(self.fd, length, offset)

        def write(self, buf, offset):
            logger.info("XmpFileWrite")
            if self.iolock:
                self.iolock.acquire()
                try:
                    self.file.seek(offset)
                    self.file.write(buf)
                    return len(buf)
                finally:
                    self.iolock.release()
            else:
                return os.pwrite(self.fd, buf, offset)

        def release(self, flags):
            logger.info(["XmpFileRelease", flags])
            self.file.close()

        def _fflush(self):
            if "w" in self.file.mode or "a" in self.file.mode:
                self.file.flush()

        def fsync(self, isfsyncfile):
            logger.info("XmpFileFSync")
            self._fflush()
            if isfsyncfile and hasattr(os, "fdatasync"):
                os.fdatasync(self.fd)
            else:
                os.fsync(self.fd)

        def flush(self):
            logger.info("XmpFileFlush")
            self._fflush()
            # cf. xmp_flush() in fusexmp_fh.c
            os.close(os.dup(self.fd))

        def fgetattr(self):
            logger.info("XmpFileFGetAttr")
            return os.fstat(self.fd)

        def ftruncate(self, len):
            logger.info("XmpFileTruncate")
            self.file.truncate(len)

        def lock(self, cmd, owner, **kw):
            logger.info(["XmpFileLock", cmd, owner])
            # The code here is much rather just a demonstration of the locking
            # API than something which actually was seen to be useful.

            # Advisory file locking is pretty messy in Unix, and the Python
            # interface to this doesn't make it better.
            # We can't do fcntl(2)/F_GETLK from Python in a platfrom independent
            # way. The following implementation *might* work under Linux.
            #
            # if cmd == fcntl.F_GETLK:
            #     import struct
            #
            #     lockdata = struct.pack('hhQQi', kw['l_type'], os.SEEK_SET,
            #                            kw['l_start'], kw['l_len'], kw['l_pid'])
            #     ld2 = fcntl.fcntl(self.fd, fcntl.F_GETLK, lockdata)
            #     flockfields = ('l_type', 'l_whence', 'l_start', 'l_len', 'l_pid')
            #     uld2 = struct.unpack('hhQQi', ld2)
            #     res = {}
            #     for i in xrange(len(uld2)):
            #          res[flockfields[i]] = uld2[i]
            #
            #     return fuse.Flock(**res)

            # Convert fcntl-ish lock parameters to Python's weird
            # lockf(3)/flock(2) medley locking API...
            op = {
                fcntl.F_UNLCK: fcntl.LOCK_UN,
                fcntl.F_RDLCK: fcntl.LOCK_SH,
                fcntl.F_WRLCK: fcntl.LOCK_EX,
            }[kw["l_type"]]
            if cmd == fcntl.F_GETLK:
                return -EOPNOTSUPP
            elif cmd == fcntl.F_SETLK:
                if op != fcntl.LOCK_UN:
                    op |= fcntl.LOCK_NB
            elif cmd == fcntl.F_SETLKW:
                pass
            else:
                return -EINVAL

            fcntl.lockf(self.fd, op, kw["l_start"], kw["l_len"])

    def main(self, *a, **kw):
        self.file_class = self.XmpFile
        return Fuse.main(self, *a, **kw)


def main():

    usage = (
        """
Userspace nullfs-alike: mirror the filesystem tree from some point on.

"""
        + Fuse.fusage
    )

    server = Xmp(
        version="%prog " + fuse.__version__, usage=usage, dash_s_do="setsingle"
    )

    server.parser.add_option(
        mountopt="root",
        metavar="PATH",
        default="/",
        help="mirror filesystem from under PATH [default: %default]",
    )
    server.parse(values=server, errex=1)

    try:
        if server.fuse_args.mount_expected():
            os.chdir(server.root)
    except OSError:
        logger.info("can't enter root of underlying filesystem", file=sys.stderr)
        sys.exit(1)

    server.main()


if __name__ == "__main__":
    main()
