import base64
from typing import cast
import logging
import stat
from algosdk.abi import ABIType
from algosdk.atomic_transaction_composer import LogicSigTransactionSigner
import beaker as bkr

from algorand.contract import NFTP, FileBlockDetails
from nftp import StorageManager, FileStat


ALGOD_HOST = "http://localhost:4001"
ALGOD_TOKEN = "a" * 64

storage_deets_codec = ABIType.from_string(str(FileBlockDetails().type_spec()))


class AlgorandStorageManager(StorageManager):
    def __init__(
        self, app_client: bkr.client.ApplicationClient, storage_size: int = 1024
    ):
        self.app_client = app_client
        self.app_client.build()
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

        app_state = self.app_client.get_application_state(raw=True)
        logging.info(f"{app_state}")

        files: dict[str, FileStat] = {}
        for fname, num_boxes in app_state.items():
            fname = self.strip_leading_zeros(fname).decode("utf-8")
            if fname not in files or num_boxes > files[fname].num_boxes:
                # Idk about the order of these being guaranteed
                fst = FileStat(num_boxes)
                fst.st_mode = stat.S_IFREG | 0o666
                fst.st_nlink = 1
                fst.st_size = self.storage_size * num_boxes
                files[fname] = fst

        return files

    def strip_leading_zeros(self, name: bytes) -> bytes:
        for idx, b in enumerate(name):
            if b != 0:
                return name[idx:]
        return b""

    def create_file(self, name: str, mode: int, dev: int):
        self._create_acct(name, 0)
        self.files = self.list_files()
        logging.debug(f"{self.files}")

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
                buf += self._read_acct(name, idx)[start_offset:stop_offset]

            buf = buf.strip(bytes(1))
            logging.debug(f"{buf.hex()}")

        else:
            buf = bytes(size)

        return buf

    def write_file(self, name: str, offset: int, buf: bytes):
        start_idx = offset // self.storage_size
        start_offset = offset % self.storage_size

        stop_idx = (offset + len(buf)) // self.storage_size
        stop_offset = (offset + len(buf)) % self.storage_size

        logging.debug(
            f"writing {len(buf)} bytes from {start_idx} : {start_offset} to {stop_idx} : {stop_offset}"
        )
        for idx in range(stop_idx - start_idx):
            box_idx = start_idx + idx
            if box_idx >= self.files[name].num_boxes:
                self._create_acct(name, box_idx)
                self.files = self.list_files()

            try:
                logging.debug(f"{buf.hex()}")
                working_buf = bytearray(
                    buf[idx * self.storage_size : (idx + 1) * self.storage_size]
                )
                logging.debug(f"working buf size: {len(working_buf)}")
                if box_idx == start_idx and start_offset > 0:
                    # Partial write, might as well read the whole storage unit
                    working_buf[:start_offset] = self._read_acct(name, box_idx)[
                        start_offset:
                    ]
                elif box_idx == stop_idx and stop_offset > 0:
                    working_buf[stop_offset:] = self._read_acct(name, box_idx)[
                        :stop_offset
                    ]

                if len(working_buf) == 0:
                    return 0

                logging.debug(f"about to write: {working_buf.hex()}")
                self._write_acct(name, box_idx, working_buf)
            except Exception as e:
                logging.error(f"Failed to write: {e}")
                raise e
        return len(buf)

    def delete_file(self, name: str):
        # refresh cache
        self.file_exists(name)
        for idx in range(self.files[name].num_boxes + 1):
            self._delete_acct(name, idx)

        del self.files[name]

    def _read_acct(self, name: str, idx: int) -> bytes:
        acct = self._storage_account(name, idx)
        logging.debug(f"{acct.lsig.address()}")

        acct_state = self.app_client.get_account_state(acct.lsig.address(), raw=True)
        logging.debug(f"{acct_state}")
        # Make sure the blob is in the right order
        return b"".join([acct_state[x.to_bytes(1, "big")] for x in range(9)])[
            : self.storage_size
        ]

    def _delete_acct(self, name: str, idx: int):
        lsig_signer = self._storage_account(name, idx)
        lsig_client = self.app_client.prepare(lsig_signer)

        deets = self._file_block_details(name, idx)

        self.app_client.call(
            NFTP.delete, deets=deets, storage_account=lsig_signer.lsig.address()
        )
        lsig_client.close_out(deets=deets)

    def _create_acct(self, name: str, idx: int):
        try:

            lsig_signer = self._storage_account(name, idx)
            lsig_addr = lsig_signer.lsig.address()

            ai = self.app_client.client.account_info(lsig_addr)
            if "amount" in ai and ai["amount"] > 0:
                return

            lsig_client = self.app_client.prepare(lsig_signer)
            self.app_client.fund(bkr.consts.algo * 2, addr=lsig_addr)
            lsig_client.opt_in(
                deets=self._file_block_details(name, idx),
                rekey_to=self.app_client.app_addr,
            )
        except Exception as e:
            logging.error(f"cant create account: {e}")
            raise e

    def _write_acct(self, name: str, idx: int, data: bytes):
        try:
            lsig_signer = self._storage_account(name, idx)
            deets = self._file_block_details(name, idx)
            self.app_client.call(
                NFTP.write,
                deets=deets,
                data=data + bytes(self.storage_size - len(data)),
                storage_account=lsig_signer.lsig.address(),
            )
        except Exception as e:
            logging.error(f"error in write: {e}")
            raise e

    def _file_block_details(self, name: str, idx: int) -> list[str | int]:
        return [bytes(32 - len(name)) + name.encode(), idx]

    def _storage_account(self, name: str, idx: int) -> LogicSigTransactionSigner:
        app = cast(NFTP, self.app_client.app)
        try:
            deets = self._file_block_details(name, idx)
            deets.append(self.app_client.app_id)
            val = app.tmpl_account.template_signer(*deets)
        except Exception as e:
            logging.error(f"wat: {e}")
            raise e
        return val

    def _acct_addr_seq(self, addr: str) -> tuple[str, int]:
        state = self.app_client.get_account_state(addr)
        return storage_deets_codec.decode(state["deets"])

    # def _read_box(self, name: str, idx: int) -> bytes:
    #    logging.debug(f"_read_box: {name} {idx}")
    #    box_name = self._box_name(name, idx)
    #    logging.debug(f"getting app box: {name} {idx}")
    #    try:
    #        box_response = self.app_client.client.application_box_by_name(
    #            self.app_client.app_id, box_name
    #        )
    #        val = base64.b64decode(box_response["value"])
    #        logging.debug(f"val: {val}")
    #    except Exception as e:
    #        logging.error(f"Failed to get box: {e}")
    #        raise e
    #    return val

    # def _delete_box(self, name: bytes, idx: int):
    #    box_name = self._box_name(name, idx)
    #    self.app_client.call(
    #        NFTP.delete_data,
    #        box_name=box_name,
    #        boxes=[[self.app_client.app_id, box_name]],
    #    )

    # def _write_box(self, name: bytes, idx: int, data: bytes):
    #    box_name = self._box_name(name, idx)
    #    data += bytes(self.storage_size - len(data))
    #    logging.debug(f"writing to {box_name.hex()} ({len(data)} bytes)")
    #    try:
    #        self.app_client.call(
    #            NFTP.put_data,
    #            box_name=box_name,
    #            data=data,
    #            boxes=[[self.app_client.app_id, box_name]],
    #        )
    #    except Exception as e:
    #        logging.error(f"Failed to write in app call: {e}")
    #        raise e

    # def _box_name(self, name: str, idx: int) -> bytes:
    #    return name.encode() + idx.to_bytes(4, "big")

    # def _box_seq(self, box_name: bytes) -> tuple[str, int]:
    #    fname = box_name[:-4].decode("utf-8")
    #    idx = int.from_bytes(box_name[-4:], "big")
    #    return [fname, idx]
