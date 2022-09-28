from pipes import Template
from typing import Literal
from beaker import *
from pyteal import *

box_size = 1024


class BlockOData(LogicSignature):
    fname = TemplateVariable(TealType.bytes)
    idx = TemplateVariable(TealType.uint64)

    def evaluate(self):
        return Approve()


class NFTP(Application):
    @opt_in
    def opt_in(self):
        return Approve()

    @external(authorize=Authorize.only(Global.creator_address()))
    def put_data(
        self, box_name: abi.DynamicBytes, data: abi.StaticBytes[Literal[2048]]
    ):
        return Seq(
            Pop(BoxCreate(box_name.get(), Int(box_size))),
            BoxReplace(box_name.get(), Int(0), data.get()),
        )

    @external(authorize=Authorize.only(Global.creator_address()))
    def delete_data(self, box_name: abi.DynamicBytes):
        return Pop(BoxDelete(box_name.get()))


def create_and_test():
    acct = sandbox.get_accounts().pop()
    ac = client.ApplicationClient(
        sandbox.get_algod_client(), NFTP(), signer=acct.signer
    )

    app_id, _, _ = ac.create()
    ac.fund(consts.algo * 100)

    with open("data.mp3", "rb") as f:
        data = f.read()

    for idx in range((len(data) // box_size) + 1):
        chunk = data[idx * box_size : (idx + 1) * box_size]
        if len(chunk) < box_size:
            chunk = bytes(box_size - len(chunk)) + chunk
        name = b"data.mp3" + idx.to_bytes(4, "big")
        ac.call(NFTP.put_data, box_name=name, data=chunk, boxes=[[app_id, name]])


if __name__ == "__main__":
    NFTP().dump("./artifacts")
