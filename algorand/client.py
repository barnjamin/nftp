from hashlib import sha256
import contract as app
from beaker import localnet, client, consts
from algosdk.logic import get_application_address
from algosdk.transaction import PaymentTxn
from algosdk.atomic_transaction_composer import TransactionWithSigner, AtomicTransactionComposer


class ClientFileBlock:
    def __init__(self, name: bytes, idx: int, data: bytes) -> None:
        self._name = name
        self.name = sha256(name).digest()
        self.idx = idx
        self.data = data

    def key(self) -> bytes:
        return self.name + self.idx.to_bytes(8, "big")

    def as_tuple(self) -> tuple[bytes, int, bytes]:
        return (self.name, self.idx, self.data)


class ClientFile:
    def __init__(self, name: bytes, data: bytes) -> None:
        self._name = name
        self.name = sha256(name).digest()
        self.data = data
        self.size = len(data)

    @staticmethod
    def from_file(fname: str) -> "ClientFile":
        with open(fname, "rb") as f:
            data = f.read()
        return ClientFile(fname.encode(), data)

    def mbr(self) -> int:
        return app._file_map_mbr + (
            app._chunk_map_mbr * ((self.size // app.STORAGE_SIZE) + 1)
        )

    def get_chunks(self) -> list[ClientFileBlock]:
        chunks = []

        nchunks = (self.size // app.STORAGE_SIZE) + 1
        for idx in range(nchunks):
            chunk = self.data[idx * app.STORAGE_SIZE : (idx + 1) * app.STORAGE_SIZE]

            # zpad the end
            if len(chunk) < app.STORAGE_SIZE:
                chunk = chunk + bytes(app.STORAGE_SIZE - len(chunk))

            chunks.append(ClientFileBlock(self.name, idx, chunk))

        return chunks


def create_and_test(app_id: int):
    acct = localnet.get_accounts().pop()
    ac = client.ApplicationClient(
        localnet.get_algod_client(), app.nftp, signer=acct.signer, app_id=app_id
    )

    if app_id == 0:
        app_id, _, _ = ac.create()
        print(f"app id: {app_id}")
        ac.fund(consts.algo * 100)


    app_addr = get_application_address(app_id)

    f = ClientFile.from_file("data.mp3")

    ptxn = TransactionWithSigner(
        txn=PaymentTxn(acct.address, ac.client.suggested_params(), app_addr, f.mbr()),
        signer=acct.signer,
    )

    ac.call(app.create_file, pay=ptxn, name=f.name, size=f.size, boxes=[(0, f.name)])

    chunks = f.get_chunks()
    for cidx in range(len(chunks)//16 + 1):
        atc = AtomicTransactionComposer()

        for idx in range(16):
            i = (cidx*16) + idx
            if i >= len(chunks): 
                continue

            chunk = chunks[i]
            ac.add_method_call(atc, app.write_chunk, chunk=chunk.as_tuple(), boxes=[(0, chunk.key()), (0, f.name)])

        atc.execute(ac.client, 4)

    for chunk in f.get_chunks():
        print(chunk.key())
        print(ac.get_box_contents(chunk.key()) )

    # read the file back out
    full_file = bytearray(b"".join([ac.get_box_contents(chunk.key()) for chunk in f.get_chunks()]))
    assert f.data.hex() == full_file[: f.size].hex()


if __name__ == "__main__":
    create_and_test(0)
