from typing import Literal

from beaker import Application, Authorize, consts
from beaker.lib.storage.box_mapping import BoxMapping

import pyteal as pt

# Each file is partitioned into 512 byte chunks
STORAGE_SIZE = 512

Bytes32 = pt.abi.StaticBytes[Literal[32]]
# fname (32b) + idx (8b)
Bytes40 = pt.abi.StaticBytes[Literal[40]]
Bytes512 = pt.abi.StaticBytes[Literal[512]]


# max chunks is 32 * 8
bitmap_zero = pt.Bytes(bytes(32))


_file_map_mbr = consts.BOX_FLAT_MIN_BALANCE + (
    (pt.abi.size_of(pt.abi.Uint64) + pt.abi.size_of(Bytes32))
    * consts.BOX_BYTE_MIN_BALANCE
)

_chunk_map_mbr = consts.BOX_FLAT_MIN_BALANCE + (
    (pt.abi.size_of(Bytes40) + pt.abi.size_of(Bytes512)) * consts.BOX_BYTE_MIN_BALANCE
)


class FileChunk(pt.abi.NamedTuple):
    hash: pt.abi.Field[Bytes32]
    idx: pt.abi.Field[pt.abi.Uint64]
    data: pt.abi.Field[Bytes512]


class FileCreate(pt.abi.NamedTuple):
    hash: pt.abi.Field[Bytes32]
    name: pt.abi.Field[pt.abi.String]


class FileMeta(pt.abi.NamedTuple):
    bitmap: pt.abi.Field[Bytes32]
    name: pt.abi.Field[pt.abi.String]


class FSState:
    # Mapping is name to occupied chunks as a bitmap
    _file_index: BoxMapping = BoxMapping(Bytes32, FileMeta)
    # Mapping is name|chunk_idx to data chunk
    _storage: BoxMapping = BoxMapping(Bytes40, Bytes512)


nftp = Application("nftp", state=FSState())


@nftp.external(authorize=Authorize.only(pt.Global.creator_address()))
def create_file(pay: pt.abi.PaymentTransaction, details: FileCreate) -> pt.Expr:
    return pt.Seq(
        # assert the payment will cover the MBR for boxes for the size of the file
        pt.Assert(pay.get().amount() >= pt.Int(_file_map_mbr)),
        # grab details for storage
        details.name.store_into(name := pt.abi.String()),
        details.hash.store_into(hash := pt.abi.make(Bytes32)),
        (zbm := pt.abi.make(Bytes32)).decode(bitmap_zero),
        (fm := FileMeta()).set(zbm, name),
        nftp.state._file_index[hash].set(fm),
    )


@nftp.external(authorize=Authorize.only(pt.Global.creator_address()))
def delete_file(hash: Bytes32) -> pt.Expr:
    return pt.Seq(
        # make sure bitmap is empty
        (fm := FileMeta()).decode(nftp.state._file_index[hash].get()),
        fm.bitmap.use(lambda bm: pt.Assert(bm.get() == bitmap_zero)),
        # nuke it
        pt.Assert(nftp.state._file_index[hash].delete()),
    )


@nftp.external(authorize=Authorize.only(pt.Global.creator_address()))
def write_chunk(chunk: FileChunk) -> pt.Expr:
    return pt.Seq(
        chunk.hash.store_into(hash := pt.abi.make(Bytes32)),
        chunk.idx.store_into(idx := pt.abi.Uint64()),
        chunk.data.store_into(data := pt.abi.make(Bytes512)),
        # write the chunk
        nftp.state._storage[chunk_key(hash, idx)].set(data.get()),
        # flip the bit to set
        (fm := FileMeta()).decode(nftp.state._file_index[hash.get()].get()),
        fm.bitmap.store_into(bm := pt.abi.make(Bytes32)),
        fm.name.store_into(name := pt.abi.String()),
        bm.decode(pt.SetBit(bm.get(), idx.get(), pt.Int(1))),
        fm.set(bm, name),
        # write the new metadata
        nftp.state._file_index[hash.get()].set(fm),
    )


@nftp.external(authorize=Authorize.only(pt.Global.creator_address()))
def delete_chunk(key: Bytes40) -> pt.Expr:
    return pt.Seq(
        (hash := pt.abi.make(Bytes32)).decode(
            pt.Extract(key.get(), pt.Int(0), pt.Int(32))
        ),
        (idx := pt.abi.Uint64()).decode(pt.Suffix(key.get(), pt.Int(32))),
        # flip the book keeping bit
        (fm := FileMeta()).decode(nftp.state._file_index[hash.get()].get()),
        fm.bitmap.store_into(bm := pt.abi.make(Bytes32)),
        fm.name.store_into(name := pt.abi.String()),
        bm.decode(pt.SetBit(bm.get(), idx.get(), pt.Int(0))),
        fm.set(bm, name),
        # write the new metadata
        nftp.state._file_index[hash.get()].set(fm),
        pt.Assert(nftp.state._storage[key].delete()),
    )


@pt.Subroutine(pt.TealType.uint64)
def file_mbr(size: pt.Expr) -> pt.Expr:
    file_map_mbr = pt.Int(_file_map_mbr)
    chunk_map_mbr = pt.Int(_chunk_map_mbr)
    return file_map_mbr + (chunk_map_mbr * ((size / pt.Int(STORAGE_SIZE)) + pt.Int(1)))


@pt.Subroutine(pt.TealType.none)
def refund_mbr(size: pt.Expr) -> pt.Expr:
    return pt.Seq(
        pt.InnerTxnBuilder.Execute(
            {
                pt.TxnField.type_enum: pt.TxnType.Payment,
                pt.TxnField.amount: pt.Int(_file_map_mbr),
                pt.TxnField.receiver: pt.Txn.sender(),
                pt.TxnField.fee: pt.Int(0),
            }
        )
    )


@pt.Subroutine(pt.TealType.bytes)
def chunk_key(name: Bytes32, idx: pt.abi.Uint64) -> pt.Expr:
    return pt.Concat(name.get(), pt.Itob(idx.get()))


@pt.Subroutine(pt.TealType.bytes)
def fname_hash(name: pt.abi.String) -> pt.Expr:
    return pt.Sha256(name.get())
