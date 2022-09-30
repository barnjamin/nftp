//#![allow(unused_mut)]
#![allow(unused_imports)]
#![allow(unused_variables)]
//#![allow(dead_code)]

use {
    near_sdk::{
        borsh::{
            self,
            BorshDeserialize,
            BorshSerialize,
        },
        collections::UnorderedMap,
        env,
        json_types::Base64VecU8,
        near_bindgen,
        Balance,
        Promise,
        PromiseOrValue,
        PublicKey,
    },
    serde::Serialize,
    std::str,
};

#[derive(BorshDeserialize, BorshSerialize)]
pub struct NFTPFile {
    mode: u64,
    dev:  u64,
    data: Vec<u8>,
}

#[near_bindgen]
#[derive(BorshDeserialize, BorshSerialize)]
pub struct NFTPBridge {
    booted:   bool,
    owner_pk: PublicKey,
    root:     UnorderedMap<String, NFTPFile>,
}

impl Default for NFTPBridge {
    fn default() -> Self {
        Self {
            booted:   false,
            owner_pk: env::signer_account_pk(),
            root:     UnorderedMap::new(b"root".to_vec()),
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

    pub fn list_files(&self) -> Vec<String> {
        let mut ret = vec![];

        for k in self.root.keys_as_vector().iter() {
            ret.push(k);
        }

        return ret;
    }

    #[payable]
    pub fn create_file(&mut self, name: String, mode: u64, dev: u64) -> PromiseOrValue<bool> {
        let mut refund = env::attached_deposit();
        let f = self.root.get(&name);

        if !f.is_some() {
            let old_used = env::storage_usage();
            self.root.insert(
                &name,
                &NFTPFile {
                    mode: mode,
                    dev:  dev,
                    data: b"".to_vec(),
                },
            );
            let new_used = env::storage_usage();

            if new_used > old_used {
                let cost = Balance::from(new_used - old_used) * env::storage_byte_cost();
                if cost > refund {
                    env::panic_str("DepositUnderflowForRegistration");
                }

                refund -= cost;
            }
            if new_used < old_used {
                env::panic_str("WhatTheHell");
            }
        }

        if refund > 0 {
            PromiseOrValue::Promise(Promise::new(env::predecessor_account_id()).transfer(refund))
        } else {
            PromiseOrValue::Value(true)
        }
    }

    pub fn read_file(&self, name: String, offset: u64, size: u64) -> Vec<u8> {
        let mut sz = size;
        let f = self.root.get(&name).expect("unknown file");

        let dlen = f.data.len() as u64;

        if offset >= dlen as u64 {
            return b"".to_vec();
        }

        if (offset + sz) > dlen {
            sz = dlen - offset;
        }

        return f.data[offset as usize..(offset + sz) as usize].to_vec();
    }

    #[payable]
    pub fn write_file(
        &mut self,
        name: String,
        offset: usize,
        buf: Vec<u8>,
    ) -> PromiseOrValue<bool> {
        let mut refund = env::attached_deposit();
        let mut f = self.root.get(&name).expect("unknown file");

        let old_used = env::storage_usage();

        let dlen = f.data.len() as usize;
        let sz = buf.len() as usize;

        let mut p = f.data[0..offset].to_vec();
        p.extend(buf);

        if dlen > (offset + sz) {
            p.extend(&f.data[(offset + sz)..].to_vec());
        }
        f.data = p;

        self.root.insert(&name, &f);

        let new_used = env::storage_usage();

        if new_used > old_used {
            let cost = Balance::from(new_used - old_used) * env::storage_byte_cost();
            if cost > refund {
                env::panic_str("DepositUnderflowForRegistration");
            }

            refund -= cost;
        }
        if new_used < old_used {
            env::panic_str("WhatTheHell");
        }

        if refund > 0 {
            PromiseOrValue::Promise(Promise::new(env::predecessor_account_id()).transfer(refund))
        } else {
            PromiseOrValue::Value(true)
        }
    }

    pub fn delete_file(&mut self, name: String) -> PromiseOrValue<bool> {
        let mut refund = env::attached_deposit();
        let f = self.root.get(&name);

        if !f.is_some() {
            let old_used = env::storage_usage();
            self.root.remove(&name);
            let new_used = env::storage_usage();

            if new_used > old_used {
                env::panic_str("WhatTheHell");
            }
            if new_used < old_used {
                refund += Balance::from(old_used - new_used) * env::storage_byte_cost();
            }
        }

        if refund > 0 {
            PromiseOrValue::Promise(Promise::new(env::predecessor_account_id()).transfer(refund))
        } else {
            PromiseOrValue::Value(true)
        }
    }
}
