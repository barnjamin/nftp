import logging
import stat
from hashlib import sha256
from algosdk.transaction import PaymentTxn
from algosdk.atomic_transaction_composer import (
    TransactionWithSigner,
)
import beaker as bkr

import algorand.contract as app
from nftp import StorageManager, FileStat


ALGOD_HOST = "http://localhost:4001"
ALGOD_TOKEN = "a" * 64


def chunk_key(name: bytes, idx: int) -> bytes:
    return name + idx.to_bytes(8, "big")


class ClientFileChunk:
    def __init__(self, hash: bytes, idx: int, data: bytes) -> None:
        self.hash = hash
        self.idx = idx
        self.data = data

    def key(self) -> bytes:
        return chunk_key(self.hash, self.idx)

    def as_tuple(self) -> tuple[bytes, int, bytes]:
        return (self.hash, self.idx, self.data)


class ClientFile:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self.hash = sha256(name.encode()).digest()
        self.data = data
        self.size = len(data)

    @staticmethod
    def from_file(fname: str) -> "ClientFile":
        with open(fname, "rb") as f:
            data = f.read()
        return ClientFile(fname, data)

    def mbr(self) -> int:
        return app._file_map_mbr + (
            app._chunk_map_mbr * ((self.size // app.STORAGE_SIZE) + 1)
        )

    def get_chunks(self) -> list[ClientFileChunk]:
        chunks = []

        nchunks = (self.size // app.STORAGE_SIZE) + 1
        for idx in range(nchunks):
            chunk = self.data[idx * app.STORAGE_SIZE : (idx + 1) * app.STORAGE_SIZE]

            # zpad the end
            if len(chunk) < app.STORAGE_SIZE:
                chunk = chunk + bytes(app.STORAGE_SIZE - len(chunk))

            chunks.append(ClientFileChunk(self.hash, idx, chunk))

        return chunks


def get_bitmap(bm: bytes) -> dict[int, bool]:
    bitmap = {}
    for byte_idx, b in enumerate(bm):
        for bit_idx in range(8):
            if b >> bit_idx > 0:
                bitmap[byte_idx * 8 + bit_idx] = True
    return bitmap


class AlgorandStorageManager(StorageManager):
    def __init__(
        self,
        app_client: bkr.client.ApplicationClient,
        storage_size: int = app.STORAGE_SIZE,
    ):
        self.app_client = app_client
        self.storage_size = storage_size
        super().__init__()

    @staticmethod
    def factory(args) -> "AlgorandStorageManager":
        acct = bkr.localnet.get_accounts().pop()
        algod_client = bkr.localnet.clients.get_algod_client()

        return AlgorandStorageManager(
            app_client=bkr.client.application_client.ApplicationClient(
                algod_client, app.nftp, signer=acct.signer, app_id=args.algorand_appid
            )
        )

    def list_files(self) -> dict[str, FileStat]:
        names = self.app_client.get_box_names()
        # only take boxes where the key is 32 bytes for fname
        fnames = [name for name in names if len(name) == 32]
        logging.debug(f"# files: {len(fnames)}")

        files: dict[str, FileStat] = {}
        for fname in fnames:
            md = self.app_client.get_box_contents(fname)

            bitmap = get_bitmap(md[:32])
            name = md[36:].decode()

            num_boxes = len(bitmap.keys())
            if fname not in files or num_boxes > files[name].num_boxes:
                # Idk about the order of these being guaranteed
                fst = FileStat(fname, num_boxes)
                fst.st_mode = stat.S_IFREG | 0o666
                fst.st_nlink = 1
                fst.st_size = self.storage_size * num_boxes
                files[name] = fst

        return files

    def create_file(self, name: str):
        logging.debug("setting files")
        try:
            self._create_file(name)
            self.files = self.list_files()
            logging.debug(f"{self.files}")
        except Exception as e:
            logging.debug(f"Failed to create: {e}")

    def read_file(self, name: str, offset: int, size: int) -> bytes:
        # refreshes our list
        self.file_exists(name)

        logging.debug(f"read file: {self.files[name].st_size}")

        buf = b""
        if offset < self.files[name].st_size:
            if offset + size > self.files[name].st_size:
                size = self.files[name].st_size - offset

            start_box = offset // self.storage_size
            start_offset = offset % self.storage_size

            stop_box = (size + offset) // self.storage_size
            stop_offset = (size + offset) % self.storage_size

            logging.debug(
                "{} {} {} {}".format(start_box, start_offset, stop_box, stop_offset)
            )

            hash = sha256(name.encode()).digest()

            for box_idx in range(start_box, stop_box - 1):
                working_buf = self._read_box(hash, box_idx)
                start, stop = 0, self.storage_size

                if box_idx == start_box and start_offset > 0:
                    start = start_offset

                if box_idx == stop_box and stop_offset > 0:
                    stop = self.storage_size - stop_offset

                buf += working_buf[start:stop]

        else:
            buf = bytes(size)

        return buf

    def write_file(self, name: str, offset: int, buf: bytes):
        start_box = offset // self.storage_size
        start_offset = offset % self.storage_size

        stop_box = (offset + len(buf)) // self.storage_size
        stop_offset = (offset + len(buf)) % self.storage_size

        num_boxes_to_write = (stop_box - start_box) + 1

        logging.debug(
            f"writing {len(buf)} bytes from {start_box} : {start_offset}"
            f" to {stop_box} : {stop_offset}"
        )

        hash = sha256(name.encode()).digest()

        cursor = 0
        for idx in range(num_boxes_to_write):
            box_idx = start_box + idx

            # copy  everything from cursor on
            to_write = buf[cursor:]

            if box_idx == start_box and start_offset > 0:
                curr_data = self._read_box(hash, box_idx)
                # take -start_offset bytes from the to_write buffer
                # since we want to fill out
                to_write = curr_data[:start_offset] + to_write[start_offset:]
                # update our cursor to show we read this many bytes
                cursor += start_offset

            elif box_idx == stop_box and stop_offset > 0:
                curr_data = self._read_box(hash, box_idx)
                to_write = to_write[:stop_offset] + curr_data[stop_offset:]
                cursor += stop_offset

            to_write = to_write[: self.storage_size]

            logging.info(f"{box_idx}: {start_offset}:{stop_offset}, {cursor}")

            if len(to_write) == 0:
                return cursor

            logging.debug(f"about to write: {len(to_write)}")
            self._write_chunk(hash, box_idx, to_write)

        return len(buf)

    def delete_file(self, name: str):
        # refresh cache
        self.file_exists(name)

        hash = sha256(name.encode()).digest()
        for idx in range(self.files[name].num_boxes):
            self._delete_box(hash, idx)

        del self.files[name]

    def _create_file(self, name: str):
        # TODO: making a fake file with default 2048 size to cover mbr
        f = ClientFile(name, bytes(2**11))

        # Create the file entry, paying for storage
        self.app_client.call(
            app.create_file,
            pay=TransactionWithSigner(
                txn=PaymentTxn(
                    self.app_client.sender,
                    self.app_client.client.suggested_params(),
                    self.app_client.app_addr,
                    f.mbr(),
                ),
                signer=self.app_client.signer,
            ),
            details=(f.hash, f.name),
            boxes=[(0, f.hash)],
        )

    def _read_box(self, hash: bytes, idx: int) -> bytes:
        box_name = chunk_key(hash, idx)
        logging.debug(f"getting app box: {box_name}")
        try:
            val = self.app_client.get_box_contents(box_name)
        except Exception as e:
            logging.error(f"Failed to get box: {e}")
            return bytes(self.storage_size)
        return val

    def _delete_box(self, hash: bytes, idx: int):
        box_name = chunk_key(hash, idx)
        try:
            self.app_client.call(
                app.delete_chunk,
                key=box_name,
                boxes=[(0, box_name), (0, hash)],
            )
        except Exception as e:
            logging.error(f"Failed to delete in app call: {e}")
            raise e

    def _write_chunk(self, hash: bytes, idx: int, data: bytes):
        chunk = ClientFileChunk(hash, idx, data)
        # zpad the data
        data += bytes(self.storage_size - len(data))

        logging.debug(f"writing to {chunk.key().hex()} ({len(data)} bytes)")
        try:
            self.app_client.call(
                app.write_chunk,
                chunk=chunk.as_tuple(),
                boxes=[(0, chunk.key()), (0, hash)],
            )
        except Exception as e:
            logging.error(f"Failed to write in app call: {e}")
            raise e
