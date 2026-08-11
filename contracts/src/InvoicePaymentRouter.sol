// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

contract InvoicePaymentRouter {
    using SafeERC20 for IERC20;

    struct PaymentRequest {
        address merchant;
        address token;
        uint256 amount;
        uint256 expiry;
        bool paid;
        bool exists;
    }

    mapping(bytes32 => PaymentRequest) private _requests;

    event InvoicePaymentCreated(
        bytes32 indexed invoiceId,
        address indexed merchant,
        address indexed token,
        uint256 amount,
        uint256 expiry
    );

    event InvoicePaid(
        bytes32 indexed invoiceId,
        address indexed payer,
        address indexed merchant,
        address token,
        uint256 amount
    );

    error InvalidInvoice();
    error AlreadyPaid();
    error Expired();
    error InvalidToken();
    error InvalidAmount();

    function createPaymentRequest(
        bytes32 invoiceId,
        address token,
        uint256 amount,
        uint256 expiry
    ) external {
        if (_requests[invoiceId].exists) revert InvalidInvoice();
        if (amount == 0) revert InvalidAmount();

        _requests[invoiceId] = PaymentRequest({
            merchant: msg.sender,
            token: token,
            amount: amount,
            expiry: expiry,
            paid: false,
            exists: true
        });

        emit InvoicePaymentCreated(invoiceId, msg.sender, token, amount, expiry);
    }

    function payInvoice(bytes32 invoiceId) external {
        PaymentRequest storage req = _requests[invoiceId];
        if (!req.exists) revert InvalidInvoice();
        if (req.paid) revert AlreadyPaid();
        if (block.timestamp > req.expiry) revert Expired();

        req.paid = true;
        IERC20(req.token).safeTransferFrom(msg.sender, req.merchant, req.amount);

        emit InvoicePaid(invoiceId, msg.sender, req.merchant, req.token, req.amount);
    }

    function getPaymentRequest(bytes32 invoiceId)
        external
        view
        returns (
            address merchant,
            address token,
            uint256 amount,
            uint256 expiry,
            bool paid,
            bool exists
        )
    {
        PaymentRequest storage req = _requests[invoiceId];
        return (req.merchant, req.token, req.amount, req.expiry, req.paid, req.exists);
    }
}
