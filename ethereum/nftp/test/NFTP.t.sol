// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "../src/NFTP.sol";

contract NFTPTest is Test {
    using stdStorage for StdStorage;

    NFTP public nftp;

    function setUp() public {
        nftp = new NFTP();
    }

    function testCreateFile(string memory fname) public {
        bytes32 hsh = sha256(bytes(fname));
        nftp.createFile(hsh, fname);

        (string memory name, bytes32 bitmap) = nftp.files(hsh);
        assertEq(name, fname);
        assertEq(bitmap, bytes32(0));
    }

    function testWriteChunk(string memory fname, uint8 idx, bytes memory data) public {
        bytes32 hsh = sha256(bytes(fname));
        nftp.createFile(hsh, fname);
        (string memory name, bytes32 bitmap) = nftp.files(hsh);
        assertEq(name, fname);

        nftp.writeChunk(hsh, idx, data);

        (, bitmap) = nftp.files(hsh);

        uint256 mask = 1 << idx;
        assertEq(uint256(bitmap) & mask, mask);

        bytes memory chunk = nftp.chunks(bytes.concat(hsh, abi.encodePacked(idx)));
        assertEq(data, chunk);
    }

    function testDeleteChunk(string memory fname, uint8 idx, bytes memory data) public {
        bytes32 hsh = sha256(bytes(fname));
        nftp.createFile(hsh, fname);
        (string memory name, bytes32 bitmap) = nftp.files(hsh);
        assertEq(name, fname);

        nftp.writeChunk(hsh, idx, data);

        assertEq(data, nftp.chunks(bytes.concat(hsh, abi.encodePacked(idx))));

        uint256 mask = 1 << idx;

        (, bitmap) = nftp.files(hsh);
        assertEq(uint256(bitmap) & mask, mask);

        nftp.deleteChunk(hsh, idx);

        (, bitmap) = nftp.files(hsh);
        assertEq(uint256(bitmap) ^ mask, mask);
    }

    //function testDeleteChunk() public {}

    //function testSetNumber(uint256 x) public {
    //    counter.setNumber(x);
    //    assertEq(counter.number(), x);
    //}
}
