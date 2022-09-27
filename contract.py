from typing import Literal
from beaker import *
from pyteal import *

box_size = 1024
class NFTP(Application):

    @external
    def put_data(self, box_name: abi.DynamicBytes, data: abi.StaticBytes[Literal[1024]]):
        return Seq(
            Pop(BoxCreate(box_name.get(), Int(box_size))),
            BoxReplace(box_name.get(),  Int(0), data.get())
        )

    @external
    def delete_data(self, box_name: abi.StaticBytes[Literal[64]]):
        return Pop(BoxDelete(box_name.get()))



if __name__ == "__main__":
    acct = sandbox.get_accounts().pop()
    ac = client.ApplicationClient(sandbox.get_algod_client(), NFTP(), signer=acct.signer, app_id=57)
    app_id, app_addr, _ = ac.create()
    print(app_id)
    print(app_addr)
    ac.fund(consts.algo * 100)

    with open("data.mp3", "rb") as f:
        data = f.read()

    for idx in range((len(data)//box_size) + 1):
        chunk = data[idx*box_size:(idx+1)*box_size]
        if len(chunk) < box_size:
            chunk = bytes(box_size - len(chunk))  + chunk
        name = b"gotcha.mp3"+idx.to_bytes(4, 'big')
        ac.call(NFTP.put_data, box_name=name, data = chunk, boxes=[[app_id, name]])
    



