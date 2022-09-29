from nftp import NftpFS
from algorand_storage_manager import AlgorandStorageManager

import fuse
from fuse import Fuse
import logging

logging.basicConfig(filename="/tmp/nftp.log", filemode="w", level=logging.DEBUG)


def main():
    ALGORAND_APP_ID = 191

    server = NftpFS(
        storage_manager=AlgorandStorageManager.from_app_id(ALGORAND_APP_ID),
        version="%prog " + fuse.__version__,
        usage="Userspace Blockchain Mounted storage example:\n" + Fuse.fusage,
        # idk what this does?
        dash_s_do="setsingle",
    )
    server.parse(errex=0)
    server.main()


if __name__ == "__main__":
    main()
