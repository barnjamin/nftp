from typing import Literal
from beaker import *
from pyteal import *

class NFTP(Application):

    @external
    def put_data(self, box_name: abi.StaticBytes[Literal[64]], data: abi.DynamicBytes):
        return Seq(
            # write data to box by name
        )

    @external
    def delete_data(self, box_name: abi.StaticBytes[Literal[64]]):
        pass


