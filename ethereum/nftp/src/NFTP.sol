// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;


struct File {
    string name;
    bytes32 bitmap;
}


contract NFTP {
    mapping(bytes32 => File) public files;
    mapping(bytes => bytes) public chunks;


    function createFile(bytes32 hsh, string memory name) public {
        files[hsh] = File({
            name: name,
            bitmap: 0
        });
    }

    function writeChunk(bytes32 hsh, uint8 idx, bytes memory data) public {
        require(data.length <= 512);

        bytes memory key = bytes.concat(hsh, abi.encodePacked(idx));
        chunks[key] = data;

        setBitTrue(hsh, idx);
    }

    function deleteChunk(bytes32 hsh, uint8 idx) public {
        bytes memory key = bytes.concat(hsh, abi.encodePacked(idx));
        delete chunks[key];

        setBitFalse(hsh, idx);
    }

    function setBitTrue(bytes32 hsh, uint8 idx) private {
        uint256 mask = 1 << idx;
        files[hsh].bitmap = files[hsh].bitmap | bytes32(mask);
    }

    function setBitFalse(bytes32 hsh, uint8 idx) private {
        uint256 mask = 1 << idx;
        files[hsh].bitmap = files[hsh].bitmap & bytes32(~mask);
    }

}
