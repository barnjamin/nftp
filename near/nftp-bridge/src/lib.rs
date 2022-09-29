//#![allow(unused_mut)]
#![allow(unused_imports)]
//#![allow(unused_variables)]
//#![allow(dead_code)]

use {
    serde::Serialize,
    near_sdk::{
        borsh::{
            self,
            BorshDeserialize,
            BorshSerialize,
        },
        collections::{
            LookupMap,
            LazyOption,
        },
        env,
        json_types::{
            Base64VecU8,
        },
        near_bindgen,
        PublicKey,
    },
    std::str,
};

#[derive(BorshDeserialize, BorshSerialize)]
pub struct NFTPFile {
    data:      Vec<u8>,
}

#[derive(BorshDeserialize, BorshSerialize)]
pub struct NFTPDir {
    data:       LookupMap<String, LazyOption<Node>>
}

#[derive(BorshSerialize, BorshDeserialize)]
pub enum NodeData {
    File(NFTPFile),
    Dir(NFTPDir),
}

#[derive(BorshSerialize, BorshDeserialize)]
pub struct Node {
    path: String,
    data: NodeData
}

impl From<NFTPFile> for NodeData {
    fn from(v: NFTPFile) -> Self {
        NodeData::File(v)
    }
}

impl From<NFTPDir> for NodeData {
    fn from(v: NFTPDir) -> Self {
        NodeData::Dir(v)
    }
}

#[near_bindgen]
#[derive(BorshDeserialize, BorshSerialize)]
pub struct NFTPBridge {
    booted:               bool,
    owner_pk:             PublicKey,
    root:                 Node,
}

impl Default for NFTPBridge {
    fn default() -> Self {
        Self {
            booted:               false,
            owner_pk:             env::signer_account_pk(),
            root:                 Node {
                path: "/".to_string(),
                data: NodeData::Dir(NFTPDir { data : LookupMap::new(b"/") } )
            }
        }
    }
}

#[near_bindgen]
impl NFTPBridge {
    pub fn boot_portal(&mut self) {
        if self.owner_pk != env::signer_account_pk() {
            env::panic_str("invalidSigner");
        }

        if self.booted {
            env::panic_str("NoDonut");
        }
        self.booted = true;
    }
}
