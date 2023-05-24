import { expect } from 'chai';
import fs from 'fs';
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
    const owner = (program.provider as anchor.AnchorProvider).wallet
    const [filePDA, _] = anchor.web3.PublicKey.findProgramAddressSync(
      [Buffer.from(testName)],
      program.programId
    );

    await program.methods
      .createFile(testName)
      .accounts({
        file: filePDA,
        authority: owner.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .rpc()


    let fileState = await program.account.file.fetch(filePDA)

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


  it('Write full file', async () => {
    const owner = (program.provider as anchor.AnchorProvider).wallet

    // Create file entry
    const fname  = "README.md"
    const [filePDA, _] = anchor.web3.PublicKey.findProgramAddressSync(
      [Buffer.from(fname)],
      program.programId
    );
    await program.methods
      .createFile(fname)
      .accounts({
        file: filePDA,
        authority: owner.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .rpc()

    let fileState = await program.account.file.fetch(filePDA)
    expect(fileState.name).to.eql(fname)
    expect(fileState.bitmap).to.eql(Array.from(new Uint8Array(32)));

    // Read in the file and chunk it
    const buff = fs.readFileSync("tests/"+fname)
    const chunks: Uint8Array[] = [];
    for(let i=0; i<buff.byteLength; i+=512){
      let chunk = buff.subarray(i, i+512)
      // Make sure the length is exactly 512 or solana pukes on serialization issues
      if (chunk.byteLength<512){
        chunk = Buffer.concat([chunk, Buffer.alloc(512 - chunk.byteLength)])
      }
      chunks.push(chunk)
    }

    // For each chunk write it to the chain
    for(let [i, b] of chunks.entries()){
      const idx = new anchor.BN(i)
      const [fileChunkPDA, _] = anchor.web3.PublicKey.findProgramAddressSync(
        [Buffer.from(fname), idx.toBuffer('be', 8)],
        program.programId
      );

      await program.methods
        .writeChunk(fname, idx, [...b])
        .accounts({
          fileChunk: fileChunkPDA,
          authority: owner.publicKey,
          systemProgram: anchor.web3.SystemProgram.programId,
        })
        .rpc()
    
      let fileState = await program.account.fileChunk.fetch(fileChunkPDA)
      expect(fileState.data).to.eql([...b])
    }



  })

});
