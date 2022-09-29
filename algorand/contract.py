from typing import Literal, cast
from beaker import *
from pyteal import *

storage_size = 1024


class FileBlock(LogicSignature):
    """Unique'd lsig to allow storage of local state bytes

    TODO: would want some nonce or other uniqueifying thing to
    prevent folks from being able to ddos by using the same logic
    and rekeying it to something else
    """

    fname = TemplateVariable(TealType.bytes)
    idx = TemplateVariable(TealType.uint64)
    z_app_id = TemplateVariable(TealType.uint64)

    def evaluate(self):
        return Approve()


class FileBlockDetails(abi.NamedTuple):
    fname: abi.Field[abi.StaticBytes[Literal[32]]]
    idx: abi.Field[abi.Uint64]


class NFTP(Application):
    files: DynamicApplicationStateValue = DynamicApplicationStateValue(
        TealType.uint64, max_keys=64
    )

    data: AccountStateBlob = AccountStateBlob(keys=9)
    deets: AccountStateValue = AccountStateValue(
        TealType.bytes, descr="Stores a tuple of name && idx for easier lookup"
    )

    tmpl_account: Precompile = Precompile(FileBlock(version=6).program)

    @opt_in
    def opt_in(self, deets: FileBlockDetails):
        """Opt File Block storage account into app"""
        fname = ScratchVar(TealType.bytes)
        return Seq(
            self.check_assert_correct_account(deets, Txn.sender()),
            Assert(
                Txn.rekey_to() == self.address, comment="Must have rekey to app address"
            ),
            self.data.initialize(),
            self.deets.set(deets.encode()),
            # Update local listing
            deets.fname.use(lambda x: fname.store(x.get())),
            self.files[fname.load()].increment(),
            Approve(),
        )

    @close_out
    def close_out(self, deets: FileBlockDetails):
        fname = ScratchVar(TealType.bytes)
        return Seq(
            deets.fname.use(lambda x: fname.store(x.get())),
            self.files[fname.load()].decrement(),
            # Last block for this file, delete it
            If(self.files[fname.load()] == Int(0), self.files[fname.load()].delete()),
            Approve(),
        )

    @external(authorize=Authorize.only(Global.creator_address()))
    def delete(self, deets: FileBlockDetails, storage_account: abi.Account):
        """rekey account back and"""
        return Seq(
            self.check_assert_correct_account(deets, storage_account.address()),
            self.rekey_back(storage_account.address()),
        )

    @external(authorize=Authorize.only(Global.creator_address()))
    def write(
        self,
        deets: FileBlockDetails,
        data: abi.StaticBytes[Literal[1024]],
        storage_account: abi.Account,
    ):
        """write data to account blob"""
        return Seq(
            # self.check_assert_correct_account(deets, storage_account.address()),
            self.data[storage_account.address()].write(Int(0), data.get()),
        )

    @internal(TealType.none)
    def rekey_back(self, addr: Expr):
        """rekey the storage account back to itself so it can close out"""
        return InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.Payment,
                TxnField.sender: addr,
                TxnField.rekey_to: addr,
            }
        )

    @internal(TealType.none)
    def check_assert_correct_account(self, deets: FileBlockDetails, acct: Expr):
        """Assert we have the right account given the file block details"""
        fname = ScratchVar()
        idx = ScratchVar()
        return Seq(
            deets.fname.use(lambda x: fname.store(x.get())),
            deets.idx.use(lambda x: idx.store(x.get())),
            Assert(
                self.tmpl_account.template_hash(
                    fname.load(), idx.load(), Global.current_application_id()
                )
                == acct
            ),
        )


def create_and_test():
    acct = sandbox.get_accounts().pop()
    ac = client.ApplicationClient(
        sandbox.get_algod_client(), NFTP(), signer=acct.signer
    )

    app_id, app_addr, _ = ac.create()
    print(f"app id: {app_id}")
    ac.fund(consts.algo * 2)

    print(f"acct: {acct.address}")
    print(f"app: {app_addr}")

    app = cast(NFTP, ac.app)

    fname = "data.mp3"
    with open(fname, "rb") as f:
        data = f.read()

    for idx in range((len(data) // storage_size) + 1):
        chunk = data[idx * storage_size : (idx + 1) * storage_size]

        if len(chunk) < storage_size:
            chunk = bytes(storage_size - len(chunk)) + chunk

        normalized_fname = bytes(32 - len(fname)) + fname.encode()
        deets = [normalized_fname, idx]

        lsig_signer = app.tmpl_account.template_signer(normalized_fname, idx, app_id)
        print(f"lsig addr: {lsig_signer.lsig.address()}")

        lsig_client = ac.prepare(signer=lsig_signer)
        try:
            lsig_client.get_account_state()
        except Exception as e:
            print(f"Not opted in yet, opting in now: {e}")
            ac.fund(consts.algo * 2, lsig_signer.lsig.address())
            lsig_client.opt_in(deets=deets, rekey_to=app_addr)
            print("after", lsig_client.get_account_state())

        print("writing")
        ac.call(
            NFTP.write,
            deets=deets,
            data=chunk,
            storage_account=lsig_signer.lsig.address(),
        )

        print("deleting")
        ac.call(NFTP.delete, deets=deets, storage_account=lsig_signer.lsig.address())
        lsig_client.close_out(deets=deets)


if __name__ == "__main__":
    create_and_test()
