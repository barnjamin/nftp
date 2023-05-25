use anchor_lang::prelude::*;

declare_id!("EdPCWzayyrWEzFLAjkaVjKivGcSVRKJYdcT7Uqf2bTxd");

#[program]
pub mod nftp {
    use super::*;

    pub fn initialize(_ctx: Context<Initialize>) -> Result<()> {
        Ok(())
    }

    pub fn create_file(ctx: Context<CreateFile>, name: String) -> Result<()> {
        ctx.accounts.file.create(name);
        Ok(())
    }

    pub fn write_chunk(
        ctx: Context<WriteFileChunk>,
        _name: String,
        _idx: u8,
        data: [u8; 512],
    ) -> Result<()> {
        ctx.accounts.file.flip_bit(_idx);
        ctx.accounts.file_chunk.data = data;
        Ok(())
    }
}

#[account]
pub struct File {
    name: String,
    // each chunk is mapped to a bit in the 32 byte array
    bitmap: [u8; 32],
}

impl File {
    pub const MAX_NAME_LENGTH: u8 = 128;
    fn create(&mut self, name: String) {
        self.name = name;
        self.bitmap = [0; 32];
    }

    fn flip_bit(&mut self, idx: u8){
        let byt: usize = usize::from(idx) / 8;
        let bit: u8 = idx % 8;

        self.bitmap[byt] ^= 1 << bit
    }
}

#[account]
pub struct FileChunk {
    pub data: [u8; 512],
}

impl FileChunk {
    pub const MAX_CHUNK_SIZE: u16 = 512;
}

#[derive(Accounts)]
#[instruction(name: String)]
pub struct CreateFile<'info> {
    #[account(
        init,
        payer=authority,
        space=8 + 128 + 32,
        seeds=[name.as_ref()],
        bump,
    )]
    pub file: Account<'info, File>,

    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(_name: String, _idx: u8)]
pub struct WriteFileChunk<'info> {
    #[account(
        init,
        payer=authority,
        space=8 + 512,
        seeds=[_name.as_ref(), _idx.to_be_bytes().as_ref()],
        bump,
        constraint = file.name == _name
    )]
    pub file_chunk: Account<'info, FileChunk>,

    #[account(mut)]
    pub file: Account<'info, File>,

    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Initialize {}
