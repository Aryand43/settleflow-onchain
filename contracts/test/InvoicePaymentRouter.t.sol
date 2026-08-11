// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {InvoicePaymentRouter} from "../src/InvoicePaymentRouter.sol";
import {MockUSDC} from "../src/MockUSDC.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract InvoicePaymentRouterTest is Test {
    InvoicePaymentRouter router;
    MockUSDC usdc;
    MockUSDC wrongToken;

    address merchant = address(0x1);
    address payer = address(0x2);

    bytes32 invoiceId = keccak256("INV-0001");
    uint256 amount = 100e6;
    uint256 expiry;

    function setUp() public {
        router = new InvoicePaymentRouter();
        usdc = new MockUSDC();
        wrongToken = new MockUSDC();
        expiry = block.timestamp + 7 days;

        vm.prank(merchant);
        router.createPaymentRequest(invoiceId, address(usdc), amount, expiry);

        usdc.mint(payer, amount);
        vm.prank(payer);
        usdc.approve(address(router), amount);
    }

    function testSuccessfulPayment() public {
        vm.expectEmit(true, true, true, true);
        emit InvoicePaymentRouter.InvoicePaid(invoiceId, payer, merchant, address(usdc), amount);

        vm.prank(payer);
        router.payInvoice(invoiceId);

        assertEq(usdc.balanceOf(merchant), amount);
        (, , , , bool paid, ) = router.getPaymentRequest(invoiceId);
        assertTrue(paid);
    }

    function testIncorrectToken() public {
        bytes32 id2 = keccak256("INV-0002");
        vm.prank(merchant);
        router.createPaymentRequest(id2, address(usdc), amount, expiry);

        wrongToken.mint(payer, amount);
        vm.prank(payer);
        wrongToken.approve(address(router), amount);

        vm.prank(payer);
        vm.expectRevert();
        router.payInvoice(id2);
    }

    function testIncorrectAmount() public {
        bytes32 id3 = keccak256("INV-0003");
        vm.prank(merchant);
        router.createPaymentRequest(id3, address(usdc), amount, expiry);

        usdc.mint(payer, amount);
        vm.prank(payer);
        usdc.approve(address(router), amount / 2);

        vm.prank(payer);
        vm.expectRevert();
        router.payInvoice(id3);
    }

    function testExpiredInvoice() public {
        bytes32 id4 = keccak256("INV-0004");
        vm.prank(merchant);
        router.createPaymentRequest(id4, address(usdc), amount, block.timestamp + 1 days);

        vm.warp(block.timestamp + 2 days);

        vm.prank(payer);
        vm.expectRevert(InvoicePaymentRouter.Expired.selector);
        router.payInvoice(id4);
    }

    function testDuplicatePayment() public {
        vm.prank(payer);
        router.payInvoice(invoiceId);

        vm.prank(payer);
        vm.expectRevert(InvoicePaymentRouter.AlreadyPaid.selector);
        router.payInvoice(invoiceId);
    }

    function testInvalidInvoice() public {
        bytes32 badId = keccak256("INVALID");
        vm.prank(payer);
        vm.expectRevert(InvoicePaymentRouter.InvalidInvoice.selector);
        router.payInvoice(badId);
    }

    function testPaymentEventEmission() public {
        vm.recordLogs();
        vm.prank(payer);
        router.payInvoice(invoiceId);
        Vm.Log[] memory entries = vm.getRecordedLogs();
        assertEq(entries.length, 2); // Transfer + InvoicePaid
    }
}
