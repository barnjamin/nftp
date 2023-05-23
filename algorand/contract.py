from typing import Literal
from hashlib import sha256

from beaker import Application, Authorize, consts
from beaker.lib.storage.box_mapping import BoxMapping

from pyteal import *

# Each file is partitioned into 512 byte chunks
STORAGE_SIZE = 512

Bytes32 = abi.StaticBytes[Literal[32]]
# fname (32b) + idx (8b)
Bytes40 = abi.StaticBytes[Literal[40]]
Bytes512 = abi.StaticBytes[Literal[512]]


_file_map_mbr = consts.BOX_FLAT_MIN_BALANCE + (
    (abi.size_of(abi.Uint64) + abi.size_of(Bytes32)) * consts.BOX_BYTE_MIN_BALANCE
)
_chunk_map_mbr = consts.BOX_FLAT_MIN_BALANCE + (
    (abi.size_of(Bytes40) + abi.size_of(Bytes512)) * consts.BOX_BYTE_MIN_BALANCE
)


class FileChunk(abi.NamedTuple):
    name: abi.Field[Bytes32]
    idx: abi.Field[abi.Uint64]
    data: abi.Field[Bytes512]


class FSState:
    # Mapping is hash name to size for chunk
    _files: BoxMapping = BoxMapping(Bytes32, abi.Uint64)
    _storage: BoxMapping = BoxMapping(Bytes40, Bytes512)


nftp = Application("nftp", state=FSState())


@nftp.external(authorize=Authorize.only(Global.creator_address()))
def create_file(pay: abi.PaymentTransaction, name: Bytes32, size: abi.Uint64) -> Expr:
    return Seq(
        # assert the payment will cover the MBR for boxes for the size of the file
        Assert(pay.get().amount() >= file_mbr(size.get())),
        # create the fname and size mapping
        nftp.state._files[name].set(size),
    )


@nftp.external(authorize=Authorize.only(Global.creator_address()))
def delete_file(name: Bytes32) -> Expr:
    # TODO: how do we know they've already deleted all the other boxes?
    return Seq(
        refund_mbr(Btoi(nftp.state._files[name].get())),
        Assert(nftp.state._files[name].delete()),
    )


@nftp.external(authorize=Authorize.only(Global.creator_address()))
def write_chunk(chunk: FileChunk) -> Expr:
    return Seq(
        chunk.name.store_into(name := abi.make(Bytes32)),
        chunk.idx.store_into(idx := abi.Uint64()),
        chunk.data.store_into(data := abi.make(Bytes512)),
        nftp.state._storage[Concat(name.get(), Itob(idx.get()))].set(data.get()),
    )


@nftp.external(authorize=Authorize.only(Global.creator_address()))
def delete_block(key: Bytes40) -> Expr:
    return Assert(nftp.state._storage[key].delete())


@Subroutine(TealType.uint64)
def file_mbr(size: Expr) -> Expr:
    file_map_mbr = Int(_file_map_mbr)
    chunk_map_mbr = Int(_chunk_map_mbr)
    return file_map_mbr + (chunk_map_mbr * ((size / Int(STORAGE_SIZE)) + Int(1)))


@Subroutine(TealType.none)
def refund_mbr(size: Expr) -> Expr:
    return Seq(
        InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.Payment,
                TxnField.amount: file_mbr(size),
                TxnField.receiver: Txn.sender(),
                TxnField.fee: Int(0),
            }
        )
    )
