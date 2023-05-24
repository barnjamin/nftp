import { expect } from 'chai';
import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { Nftp } from "../target/types/nftp";

describe("nftp", () => {
  // Configure the client to use the local cluster.
  anchor.setProvider(anchor.AnchorProvider.env());

  const program = anchor.workspace.Nftp as Program<Nftp>;

  const testName = "test_name"

  it("Is initialized!", async () => {
    // Add your test here.
    const tx = await program.methods.initialize().rpc();
    console.log("Your transaction signature", tx);
  });

  it('Create file!', async () => {
    const fileKeypair = anchor.web3.Keypair.generate()
    const owner = (program.provider as anchor.AnchorProvider).wallet

    await program.methods
      .createFile(testName)
      .accounts({
        file: fileKeypair.publicKey,
        authority: owner.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .signers([fileKeypair])
      .rpc()


    let fileState = await program.account.file.fetch(fileKeypair.publicKey)



    expect(fileState.name).to.eql(testName)
    expect(fileState.bitmap).to.eql(Array.from(new Uint8Array(32)));
  })

  it('Write file chunk!', async () => {
    const owner = (program.provider as anchor.AnchorProvider).wallet

    const buff = Array.from(new Uint8Array(512));
    const idx = new anchor.BN(0)

    const [fileChunkPDA, _] = anchor.web3.PublicKey.findProgramAddressSync(
      [Buffer.from(testName), idx.toBuffer('be', 8)],
      program.programId
    );


    await program.methods
      .writeChunk(testName, idx, buff)
      .accounts({
        fileChunk: fileChunkPDA,
        authority: owner.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .rpc()


    let fileState = await program.account.fileChunk.fetch(fileChunkPDA)

    expect(fileState.data).to.eql(buff)
  })



});
