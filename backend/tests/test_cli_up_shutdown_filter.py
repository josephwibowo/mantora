"""Tests for suppressing noisy shutdown tracebacks in `mantora up`."""

from __future__ import annotations

import asyncio
import logging

from mantora.cli.up import NoisyShutdownFilter


def _record_with_exc(exc: BaseException) -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="boom",
        args=(),
        exc_info=(type(exc), exc, None),
    )


def test_noisy_shutdown_filter_suppresses_keyboard_interrupt() -> None:
    noisy_filter = NoisyShutdownFilter()
    assert noisy_filter.filter(_record_with_exc(KeyboardInterrupt())) is False


def test_noisy_shutdown_filter_suppresses_cancelled_error() -> None:
    noisy_filter = NoisyShutdownFilter()
    assert noisy_filter.filter(_record_with_exc(asyncio.CancelledError())) is False


def test_noisy_shutdown_filter_suppresses_exception_group_of_shutdown_noise() -> None:
    noisy_filter = NoisyShutdownFilter()
    exc = BaseExceptionGroup("shutdown", [KeyboardInterrupt(), asyncio.CancelledError()])
    assert noisy_filter.filter(_record_with_exc(exc)) is False


def test_noisy_shutdown_filter_does_not_suppress_regular_exceptions() -> None:
    noisy_filter = NoisyShutdownFilter()
    assert noisy_filter.filter(_record_with_exc(ValueError("nope"))) is True
