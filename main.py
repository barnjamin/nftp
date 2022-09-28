from nftp import NftpFS
from algorand_storage_manager import AlgorandStorageManager

import fuse
from fuse import Fuse
import logging


def main():

    logging.basicConfig(filename="/tmp/nftp.log", filemode="w", level=logging.DEBUG)
    logging.info("hi")

    ALGORAND_APP_ID = 125

    server = NftpFS(
        storage_manager=AlgorandStorageManager.from_app_id(ALGORAND_APP_ID),
        version="%prog " + fuse.__version__,
        usage="Userspace Blockchain Mounted storage example:\n" + Fuse.fusage,
        # idk what this does?
        dash_s_do="setsingle",
    )
    logging.info("h0")

    server.parse(errex=0)
    logging.info("he")
    server.main()
    logging.info("hay")


if __name__ == "__main__":
    main()
