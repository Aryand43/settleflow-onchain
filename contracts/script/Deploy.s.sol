// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {InvoicePaymentRouter} from "../src/InvoicePaymentRouter.sol";
import {MockUSDC} from "../src/MockUSDC.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerPrivateKey);

        MockUSDC usdc = new MockUSDC();
        InvoicePaymentRouter router = new InvoicePaymentRouter();

        vm.stopBroadcast();

        console.log("MockUSDC:", address(usdc));
        console.log("InvoicePaymentRouter:", address(router));
    }
}
