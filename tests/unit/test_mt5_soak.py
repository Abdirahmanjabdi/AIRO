from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest
from sentinel.bridge.mt5_relay import MT5BridgeRelay, TradeTelemetry, BrainDecision

@pytest.mark.asyncio
async def test_mt5_bridge_reconnect_throttle():
    """Test that MT5 re-initialization is throttled when connection fails."""
    relay = MT5BridgeRelay()
    relay._monitor_user_id = "test-user"
    relay._mt5_ready = False
    relay._mt5_last_retry_ts = 0.0
    relay._mt5_retry_interval = 30.0

    with patch.object(relay, "_ensure_mt5_connected") as mock_ensure:
        with patch("sentinel.bridge.mt5_history.mt5", None):
            await relay._poll_mt5_for_signal()
            assert mock_ensure.called
            mock_ensure.reset_mock()
            
            relay._mt5_last_retry_ts = time_now()
            await relay._poll_mt5_for_signal()
            assert not mock_ensure.called

def time_now():
    import time
    return time.time()

@pytest.mark.asyncio
async def test_mt5_failsafe_close_all():
    """Test that 5 consecutive failures triggers fail_safe close_all."""
    relay = MT5BridgeRelay()
    relay._monitor_user_id = "test-user"
    relay._mt5_ready = True
    relay._mt5_failure_count = 4  # Next failure will trigger failsafe

    mock_mt5 = MagicMock()
    mock_mt5.positions_get.side_effect = Exception("MT5 error")
    mock_mt5.terminal_info.return_value = None  # Disconnected

    with patch("sentinel.bridge.mt5_relay.ENFORCE_MODE", True), \
         patch.object(relay, "_fail_safe_close_all") as mock_failsafe:
        with patch("sentinel.bridge.mt5_history.mt5", mock_mt5):
            res = await relay._poll_mt5_for_signal()
            assert res is None
            assert relay._mt5_failure_count == 5
            mock_failsafe.assert_called_once()

@pytest.mark.asyncio
async def test_mt5_partial_close_and_rejections():
    """Test position reduction and order_send rejection tracking."""
    relay = MT5BridgeRelay()
    mock_mt5 = MagicMock()
    mock_mt5.positions_get.return_value = [
        MagicMock(symbol="EURUSD", volume=1.0, ticket=12345, type=0) # POSITION_TYPE_BUY = 0
    ]
    mock_mt5.POSITION_TYPE_BUY = 0
    mock_mt5.TRADE_ACTION_DEAL = 1
    mock_mt5.ORDER_TYPE_SELL = 1
    mock_mt5.ORDER_TYPE_BUY = 0
    mock_mt5.ORDER_TIME_GTC = 0
    mock_mt5.ORDER_FILLING_IOC = 1
    mock_mt5.TRADE_RETCODE_DONE = 10009
    
    mock_tick = MagicMock()
    mock_tick.bid = 1.1000
    mock_tick.ask = 1.1005
    mock_mt5.symbol_info_tick.return_value = mock_tick

    # 1. Success case
    mock_result = MagicMock()
    mock_result.retcode = 10009 # DONE
    mock_mt5.order_send.return_value = mock_result

    with patch("sentinel.bridge.mt5_history.mt5", mock_mt5), \
         patch("sentinel.bridge.mt5_relay.ENFORCE_MODE", True), \
         patch("sentinel.infra.redis_cache.cache_manager.acquire_intervention_lock", return_value=True):
        
        await relay._reduce_position("EURUSD", 0.4)
        mock_mt5.order_send.assert_called_once()
        sent_req = mock_mt5.order_send.call_args[0][0]
        assert sent_req["position"] == 12345
        assert sent_req["volume"] == 0.4
        assert sent_req["type"] == mock_mt5.ORDER_TYPE_SELL

    # 2. Rejection case
    mock_mt5.order_send.reset_mock()
    mock_result.retcode = 10004 # REJECT
    
    with patch("sentinel.bridge.mt5_history.mt5", mock_mt5), \
         patch("sentinel.bridge.mt5_relay.ENFORCE_MODE", True), \
         patch("sentinel.infra.redis_cache.cache_manager.acquire_intervention_lock", return_value=True), \
         patch("logging.Logger.error") as mock_log_err:
        
        await relay._reduce_position("EURUSD", 0.4)
        mock_mt5.order_send.assert_called_once()
        mock_log_err.assert_called_with("MT5 close order failed for %s ticket %s: %s", "EURUSD", 12345, mock_result)
