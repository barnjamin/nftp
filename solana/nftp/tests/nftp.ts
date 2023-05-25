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

    const buff = new Uint8Array(512);
    const idx = new anchor.BN(0)

    const [filePDA, ] = anchor.web3.PublicKey.findProgramAddressSync(
      [Buffer.from(testName)],
      program.programId
    );

    const [fileChunkPDA, ] = anchor.web3.PublicKey.findProgramAddressSync(
      [Buffer.from(testName), idx.toBuffer('be', 1)],
      program.programId
    );


    await program.methods
      .writeChunk(testName, idx.toNumber(), [...buff])
      .accounts({
        file: filePDA,
        fileChunk: fileChunkPDA,
        authority: owner.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .rpc()


    let fileState = await program.account.fileChunk.fetch(fileChunkPDA)
    expect(fileState.data).to.eql([...buff])
  })


  it('Write full file', async () => {
    const owner = (program.provider as anchor.AnchorProvider).wallet

    // Create file entry
    const fname = "README.md"
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

    // Read in the file and chunk it into 
    // chunks of size 512 bytes exactly
    const buff = fs.readFileSync("tests/" + fname)
    const chunks: Buffer[] = [];
    for (let i = 0; i < buff.byteLength; i += 512) {
      let chunk = buff.subarray(i, i + 512)
      // Make sure the length is exactly 512 or solana pukes on serialization issues
      if (chunk.byteLength < 512) {
        chunk = Buffer.concat([chunk, Buffer.alloc(512 - chunk.byteLength)])
      }
      chunks.push(chunk)
    }

    // For each chunk write it to the chain
    for (let [i, b] of chunks.entries()) {
      const idx = new anchor.BN(i)
      const [fileChunkPDA, _] = anchor.web3.PublicKey.findProgramAddressSync(
        [Buffer.from(fname), idx.toBuffer('be', 1)],
        program.programId
      );

      // Write the chunk
      await program.methods
        .writeChunk(fname, idx.toNumber(), [...b])
        .accounts({
          file: filePDA,
          fileChunk: fileChunkPDA,
          authority: owner.publicKey,
          systemProgram: anchor.web3.SystemProgram.programId,
        })
        .rpc()

      let fileChunkState = await program.account.fileChunk.fetch(fileChunkPDA)
      expect(fileChunkState.data).to.eql([...b])

       let fileState = await program.account.file.fetch(filePDA)
       expect(fileState.bitmap).to.eql([1, ...new Uint8Array(31)])
    }
  })
});
