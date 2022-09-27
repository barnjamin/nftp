//#![allow(unused_mut)]
#![allow(unused_imports)]
//#![allow(unused_variables)]
//#![allow(dead_code)]

use {
    near_sdk::{
        borsh::{
            self,
            BorshDeserialize,
            BorshSerialize,
        },
        collections::{
            UnorderedSet,
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

#[near_bindgen]
#[derive(BorshDeserialize, BorshSerialize)]
pub struct NFTPBridge {
    booted:               bool,
    owner_pk:             PublicKey,
}

impl Default for NFTPBridge {
    fn default() -> Self {
        Self {
            booted:               false,
            owner_pk:             env::signer_account_pk(),
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
