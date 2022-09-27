import base64
import os, stat, errno
import algosdk

import fuse
from fuse import Fuse

fuse.fuse_python_api = (0, 2)
class MyStat(fuse.Stat):
    def __init__(self):
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

class HelloFS(Fuse):

    def __init__(self, app_id: int = 0, algod_host: str = "", algod_token: str = "", **kwargs):
        super().__init__(**kwargs)

        self.app_id = app_id
        self.client = algosdk.v2client.algod.AlgodClient(algod_token, algod_host)
        self.files: dict[str, int] = {}

        self.init_file_structure()


    def init_file_structure(self):
        boxes = self.client.application_boxes(self.app_id)
        for box in boxes['boxes']:
            name = base64.b64decode(box['name'])
            fname = name[:-4].decode('utf-8')
            idx = int.from_bytes(name[-4:], 'big')

            if fname not in self.files or idx > self.files[fname] :
                self.files[fname] = idx

    
    def getattr(self, path):
        print("hi getattr")
        st = MyStat()
        if path == '/':
            st.st_mode = stat.S_IFDIR | 0o755
            st.st_nlink = 2
        elif path[1:] in self.files:
            st.st_mode = stat.S_IFREG | 0o444
            st.st_nlink = 1
            st.st_size = self.files[path[1:]]  * 1024
        else:
            return -errno.ENOENT

        return st

    def readdir(self, path, offset):
        print("hi readdir")
        for r in  ['.', '..'] +  list(self.files.keys()):
            yield fuse.Direntry(r)

    def open(self, path, flags):
        print("hi open")
        if path[1:] not in self.files:
            return -errno.ENOENT

        return 0


    def read(self, path, size, offset):
        slen = self.files[path[1:]] * 1024

        buf = b''
        if offset < slen:
            if offset + size > slen:
                size = slen - offset

            offset_pos = offset % 1024
            offset_idx = offset // 1024
            iters = (size // 1024) + 1

            for chunk in range(iters):
                box_name = path[1:].encode() + (offset_idx + chunk).to_bytes(4, 'big')
                box = self.client.application_box_by_name(self.app_id, box_name) 
                buf += base64.b64decode(box['value'])

            buf = buf[offset_pos:offset_pos+size]
        else:
            buf = bytes(size) 
        return buf

    def unlink(self, path):
        return 0

    def mkdir(self, path, mode):
        return 0
   
    def rmdir(self, path):
        return 0

def main():
    usage="""
Userspace hello example
""" + Fuse.fusage
    server = HelloFS(app_id=125, algod_host="http://localhost:4001", algod_token="a"*64,
                    version="%prog " + fuse.__version__,
                     usage=usage,
                     dash_s_do='setsingle')

    server.parse(errex=1)
    server.main()

if __name__ == '__main__':
    main()