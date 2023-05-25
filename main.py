from nftp import NftpFS
from algorand_storage_manager import AlgorandStorageManager

import fuse
from fuse import Fuse

import logging
import argparse

logging.basicConfig(filename="/tmp/nftp.log", filemode="w", level=logging.DEBUG)


def main():
    parser = argparse.ArgumentParser(description="nftp setup")

    parser.add_argument("--algorand", action="store_true", help="run algorand engine")
    parser.add_argument("--algorand_appid", type=int, help="algorand appid", default=0)

    parser.add_argument("--near", action="store_true", help="run near engine")
    parser.add_argument(
        "--near_account", type=str, help="near account", default="near.test"
    )

    args, unknown = parser.parse_known_args()

    storage_manager = None

    if args.algorand:
        storage_manager = AlgorandStorageManager.factory(args)
        logging.debug(f"Using app id: {storage_manager.app_client.app_id}")
    # if args.near:
    #    storage_manager = NearStorageManager.factory(args)

    if storage_manager is None:
        parser.print_help()
        return

    server = NftpFS(
        storage_manager=storage_manager,
        version="%prog " + fuse.__version__,
        usage="Userspace Blockchain Mounted storage example:\n" + Fuse.fusage,
        # idk what this does?
        dash_s_do="setsingle",
    )
    server.parse(unknown, errex=1)
    return server.main()


if __name__ == "__main__":
    main()
