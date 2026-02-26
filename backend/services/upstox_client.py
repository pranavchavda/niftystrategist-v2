"""Upstox API client using the official SDK."""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import upstox_client
from upstox_client.rest import ApiException

from models.analysis import OHLCVData
from models.trading import Portfolio, PortfolioPosition, TradeResult

logger = logging.getLogger(__name__)


class UpstoxClient:
    """
    Client for Upstox API using the official Python SDK.

    Supports both real API calls and paper trading mode.
    In paper trading mode, market data is fetched from Upstox but orders are simulated.
    """

    # NSE stock symbol to ISIN mapping (expandable)
    SYMBOL_TO_ISIN = {
        "RELIANCE": "INE002A01018",
        "TCS": "INE467B01029",
        "INFY": "INE009A01021",
        "HDFCBANK": "INE040A01034",
        "ICICIBANK": "INE090A01021",
        "SBIN": "INE062A01020",
        "BHARTIARTL": "INE397D01024",
        "ITC": "INE154A01025",
        "KOTAKBANK": "INE237A01028",
        "LT": "INE018A01030",
        "HINDUNILVR": "INE030A01027",
        "AXISBANK": "INE238A01034",
        "BAJFINANCE": "INE296A01024",
        "MARUTI": "INE585B01010",
        "WIPRO": "INE075A01022",
        "TATAMOTORS": "INE155A01022",
        "TATASTEEL": "INE081A01020",
        "SUNPHARMA": "INE044A01036",
        "ONGC": "INE213A01029",
        "NTPC": "INE733E01010",
        # Nifty 50 additional stocks
        "ADANIENT": "INE423A01024",
        "ADANIPORTS": "INE742F01042",
        "ASIANPAINT": "INE021A01026",
        "BAJAJ-AUTO": "INE917I01010",
        "BAJAJFINSV": "INE918I01018",
        "BPCL": "INE541A01028",
        "BRITANNIA": "INE216A01030",
        "CIPLA": "INE059A01026",
        "COALINDIA": "INE522F01014",
        "DIVISLAB": "INE361B01024",
        "DRREDDY": "INE089A01023",
        "EICHERMOT": "INE066A01021",
        "GRASIM": "INE047A01021",
        "HCLTECH": "INE860A01027",
        "HDFC": "INE001A01036",
        "HDFCLIFE": "INE795G01014",
        "HEROMOTOCO": "INE158A01026",
        "HINDALCO": "INE038A01020",
        "INDUSINDBK": "INE095A01012",
        "JSWSTEEL": "INE019A01038",
        "M&M": "INE101A01026",
        "NESTLEIND": "INE239A01016",
        "POWERGRID": "INE752E01010",
        "SBILIFE": "INE123W01016",
        "SHREECEM": "INE070A01015",
        "TATACONSUM": "INE192A01025",
        "TECHM": "INE669C01036",
        "TITAN": "INE280A01028",
        "ULTRACEMCO": "INE481G01011",
        "UPL": "INE628A01036",
    }

    # Index instrument keys (not ISIN-based)
    INDEX_KEYS = {
        "NIFTY 50": "NSE_INDEX|Nifty 50",
        "BANK NIFTY": "NSE_INDEX|Nifty Bank",
        "INDIA VIX": "NSE_INDEX|INDIA VIX",
        "SENSEX": "BSE_INDEX|SENSEX",
    }

    # Symbol to company name mapping (Nifty 50)
    SYMBOL_TO_COMPANY = {
        "RELIANCE": "Reliance Industries",
        "TCS": "Tata Consultancy Services",
        "INFY": "Infosys",
        "HDFCBANK": "HDFC Bank",
        "ICICIBANK": "ICICI Bank",
        "SBIN": "State Bank of India",
        "BHARTIARTL": "Bharti Airtel",
        "ITC": "ITC",
        "KOTAKBANK": "Kotak Mahindra Bank",
        "LT": "Larsen & Toubro",
        "HINDUNILVR": "Hindustan Unilever",
        "AXISBANK": "Axis Bank",
        "BAJFINANCE": "Bajaj Finance",
        "MARUTI": "Maruti Suzuki",
        "WIPRO": "Wipro",
        "TATAMOTORS": "Tata Motors",
        "TATASTEEL": "Tata Steel",
        "SUNPHARMA": "Sun Pharma",
        "ONGC": "ONGC",
        "NTPC": "NTPC",
        "ADANIENT": "Adani Enterprises",
        "ADANIPORTS": "Adani Ports",
        "ASIANPAINT": "Asian Paints",
        "BAJAJ-AUTO": "Bajaj Auto",
        "BAJAJFINSV": "Bajaj Finserv",
        "BPCL": "Bharat Petroleum",
        "BRITANNIA": "Britannia Industries",
        "CIPLA": "Cipla",
        "COALINDIA": "Coal India",
        "DIVISLAB": "Divi's Laboratories",
        "DRREDDY": "Dr. Reddy's Laboratories",
        "EICHERMOT": "Eicher Motors",
        "GRASIM": "Grasim Industries",
        "HCLTECH": "HCL Technologies",
        "HDFC": "HDFC",
        "HDFCLIFE": "HDFC Life Insurance",
        "HEROMOTOCO": "Hero MotoCorp",
        "HINDALCO": "Hindalco Industries",
        "INDUSINDBK": "IndusInd Bank",
        "JSWSTEEL": "JSW Steel",
        "M&M": "Mahindra & Mahindra",
        "NESTLEIND": "Nestle India",
        "POWERGRID": "Power Grid Corp",
        "SBILIFE": "SBI Life Insurance",
        "SHREECEM": "Shree Cement",
        "TATACONSUM": "Tata Consumer Products",
        "TECHM": "Tech Mahindra",
        "TITAN": "Titan Company",
        "ULTRACEMCO": "UltraTech Cement",
        "UPL": "UPL",
    }

    # SDK interval mapping: our interval -> (unit, interval_value)
    INTERVAL_MAP = {
        "1minute": ("minutes", 1),
        "5minute": ("minutes", 5),
        "15minute": ("minutes", 15),
        "30minute": ("minutes", 30),
        "day": ("days", 1),
        "1d": ("days", 1),
    }

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        redirect_uri: str | None = None,
        access_token: str | None = None,
        paper_trading: bool = True,
        user_id: int = 1,
    ):
        """
        Initialize the Upstox client.

        Args:
            api_key: Upstox API key (or from UPSTOX_API_KEY env var)
            api_secret: Upstox API secret (or from UPSTOX_API_SECRET env var)
            redirect_uri: OAuth redirect URI (or from UPSTOX_REDIRECT_URI env var)
            access_token: Pre-existing access token (or from UPSTOX_ACCESS_TOKEN env var)
            paper_trading: If True, simulate orders instead of placing real ones
            user_id: User ID for paper trading (default: 1)
        """
        self.api_key = api_key or os.getenv("UPSTOX_API_KEY")
        self.api_secret = api_secret or os.getenv("UPSTOX_API_SECRET")
        self.redirect_uri = redirect_uri or os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:5173/auth/upstox/callback")
        self.paper_trading = paper_trading
        self.user_id = user_id
        self.access_token: str | None = access_token or os.getenv("UPSTOX_ACCESS_TOKEN")

        # Configure SDK
        self._configuration = upstox_client.Configuration()
        if self.access_token:
            self._configuration.access_token = self.access_token
            logger.info("Upstox SDK configured with access token")
        else:
            logger.warning("No Upstox access token - API calls will fail until token is set")

        # Paper trading state (will be loaded from DB)
        self._paper_portfolio: Portfolio | None = None
        self._paper_order_id = 1000
        self._portfolio_loaded = False

        # Dynamic symbol→instrument_key cache (populated from holdings/positions)
        self._dynamic_symbols: dict[str, str] = {}

    async def _ensure_valid_token(self) -> None:
        """
        Ensure we have a valid access token.
        If current token is missing or expired, try to load a fresh one from the DB.
        """
        if self.access_token:
            return  # Already have a token (may be expired but let API tell us)

        # Try to get a valid token from any authenticated user in the DB
        try:
            from database.session import get_db_session
            from database.models import User as DBUser
            from utils.encryption import decrypt_token
            from sqlalchemy import select

            async with get_db_session() as session:
                result = await session.execute(
                    select(DBUser)
                    .where(DBUser.upstox_access_token.isnot(None))
                    .where(DBUser.upstox_token_expiry > datetime.utcnow())
                    .order_by(DBUser.upstox_token_expiry.desc())
                    .limit(1)
                )
                db_user = result.scalar_one_or_none()

                if db_user:
                    token = decrypt_token(db_user.upstox_access_token)
                    if token:
                        self.access_token = token
                        self._configuration.access_token = token
                        logger.info(f"Loaded valid Upstox token from user {db_user.id}")
                        return

            logger.warning("No valid Upstox token found in DB")
        except Exception as e:
            logger.error(f"Failed to load token from DB: {e}")

    async def _ensure_portfolio_loaded(self) -> None:
        """Load portfolio from database if not already loaded."""
        if self._portfolio_loaded and self._paper_portfolio:
            return

        try:
            from services.trade_persistence import get_trade_persistence
            persistence = get_trade_persistence()

            if persistence:
                self._paper_portfolio = await persistence.get_portfolio_for_user(self.user_id)
                self._portfolio_loaded = True
                logger.info(f"[UpstoxClient] Loaded portfolio from DB for user {self.user_id}")
            else:
                # Fallback to default portfolio if persistence not initialized
                self._paper_portfolio = Portfolio(
                    total_value=1000000.0,
                    available_cash=1000000.0,
                    invested_value=0.0,
                    day_pnl=0.0,
                    day_pnl_percentage=0.0,
                    total_pnl=0.0,
                    total_pnl_percentage=0.0,
                    positions=[],
                )
                self._portfolio_loaded = True
                logger.warning("[UpstoxClient] Trade persistence not available, using default portfolio")
        except Exception as e:
            logger.error(f"[UpstoxClient] Failed to load portfolio from DB: {e}")
            # Fallback to default
            self._paper_portfolio = Portfolio(
                total_value=1000000.0,
                available_cash=1000000.0,
                invested_value=0.0,
                day_pnl=0.0,
                day_pnl_percentage=0.0,
                total_pnl=0.0,
                total_pnl_percentage=0.0,
                positions=[],
            )
            self._portfolio_loaded = True

    async def close(self) -> None:
        """Close any resources (SDK handles cleanup automatically)."""
        pass

    def _get_instrument_key(self, symbol: str) -> str:
        """Get the instrument key for a symbol.

        Resolution order:
        1. Hardcoded Nifty 50 map (instant)
        2. Dynamic cache from live holdings/positions
        3. NSE instruments cache (any NSE symbol)
        """
        sym = symbol.upper()

        # Check index keys first
        if sym in self.INDEX_KEYS:
            return self.INDEX_KEYS[sym]

        isin = self.SYMBOL_TO_ISIN.get(sym)
        if isin:
            return f"NSE_EQ|{isin}"

        # Fallback: dynamic cache from holdings
        if sym in self._dynamic_symbols:
            return self._dynamic_symbols[sym]

        # Fallback: instruments cache (covers all NSE symbols)
        from services.instruments_cache import get_instrument_key as cache_get_key
        cached_key = cache_get_key(sym)
        if cached_key:
            return cached_key

        raise ValueError(
            f"No instrument mapping for symbol '{symbol}'. "
            f"Use nf-quote --search to find valid NSE symbols."
        )

    def set_access_token(self, token: str) -> None:
        """Set the access token directly."""
        self.access_token = token
        self._configuration.access_token = token

    # OAuth Authentication

    def get_auth_url(self) -> str:
        """Get the Upstox OAuth authorization URL."""
        if not self.api_key:
            raise ValueError("UPSTOX_API_KEY not configured")
        base_url = "https://api.upstox.com/v2/login/authorization/dialog"
        params = {
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
        }
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base_url}?{query_string}"

    async def exchange_code_for_token(self, code: str) -> str:
        """Exchange authorization code for access token using SDK."""
        if not self.api_key or not self.api_secret:
            raise ValueError("UPSTOX_API_KEY and UPSTOX_API_SECRET must be configured")

        try:
            api_client = upstox_client.ApiClient(self._configuration)
            login_api = upstox_client.LoginApi(api_client)

            response = login_api.token(
                api_version="v2",
                code=code,
                client_id=self.api_key,
                client_secret=self.api_secret,
                redirect_uri=self.redirect_uri,
                grant_type="authorization_code",
            )

            if response and response.access_token:
                self.set_access_token(response.access_token)
                logger.info("Successfully obtained access token from Upstox")
                return response.access_token
            else:
                raise ValueError("No access token in response")

        except ApiException as e:
            raise ValueError(f"Token exchange failed: {e.status} - {e.reason}. {e.body}")
        except Exception as e:
            raise ValueError(f"Token exchange failed: {e}")

    # Market Data

    async def get_historical_data(
        self,
        symbol: str,
        interval: Literal["1minute", "5minute", "15minute", "30minute", "day"] = "15minute",
        days: int = 30,
    ) -> list[OHLCVData]:
        """
        Get historical OHLCV data for a symbol using SDK.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE", "INFY")
            interval: Candle interval
            days: Number of days of history

        Returns:
            List of OHLCV candles

        Raises:
            ValueError: If no access token, no ISIN mapping, or API error
        """
        await self._ensure_valid_token()
        if not self.access_token:
            raise ValueError(
                f"No Upstox access token configured. Please connect your Upstox account in Settings."
            )

        instrument_key = self._get_instrument_key(symbol)
        unit, interval_value = self.INTERVAL_MAP.get(interval, ("days", 1))

        # Calculate date range
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        logger.info(f"Fetching {symbol} ({instrument_key}) {interval_value} {unit} candles from {from_date} to {to_date}")

        try:
            api_client = upstox_client.ApiClient(self._configuration)
            history_api = upstox_client.HistoryV3Api(api_client)

            # Use intraday endpoint for today's minute-level data (days <= 1),
            # historical endpoint for multi-day ranges (including 5D with minute intervals).
            # If intraday returns nothing (market closed / weekend), fall back to
            # historical with a wider window to show the last trading day's candles.
            candles_data = []
            if days <= 1 and unit == "minutes":
                response = history_api.get_intra_day_candle_data(
                    instrument_key=instrument_key,
                    unit=unit,
                    interval=interval_value,
                )
                candles_data = response.data.candles if response.data else []

                if not candles_data:
                    # Market closed — fall back to last 4 days to cover weekends/holidays
                    logger.info(f"Intraday empty for {symbol}, falling back to historical (last 4 days)")
                    fallback_from = (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d")
                    response = history_api.get_historical_candle_data1(
                        instrument_key=instrument_key,
                        unit=unit,
                        interval=interval_value,
                        to_date=to_date,
                        from_date=fallback_from,
                    )
                    candles_data = response.data.candles if response.data else []
                    # Keep only the most recent trading day's candles
                    if candles_data:
                        last_day = candles_data[0][0][:10]
                        candles_data = [c for c in candles_data if c[0][:10] == last_day]
            else:
                response = history_api.get_historical_candle_data1(
                    instrument_key=instrument_key,
                    unit=unit,
                    interval=interval_value,
                    to_date=to_date,
                    from_date=from_date,
                )
                candles_data = response.data.candles if response.data else []

            if not candles_data:
                raise ValueError(f"No candle data returned for {symbol}. Market may be closed or symbol invalid.")

            candles = []
            for candle in candles_data:
                # SDK returns: [timestamp, open, high, low, close, volume, oi]
                candles.append(
                    OHLCVData(
                        timestamp=candle[0] if isinstance(candle[0], str) else candle[0].isoformat(),
                        open=float(candle[1]),
                        high=float(candle[2]),
                        low=float(candle[3]),
                        close=float(candle[4]),
                        volume=int(candle[5]),
                    )
                )

            logger.info(f"Fetched {len(candles)} candles for {symbol}")
            return candles

        except ApiException as e:
            raise ValueError(f"Upstox API error for {symbol}: {e.status} - {e.reason}. {e.body}")
        except Exception as e:
            raise ValueError(f"Failed to fetch data for {symbol}: {e}")

    async def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol using SDK."""
        await self._ensure_valid_token()
        if not self.access_token:
            raise ValueError(f"No Upstox access token configured. Please connect your Upstox account in Settings.")

        instrument_key = self._get_instrument_key(symbol)

        try:
            api_client = upstox_client.ApiClient(self._configuration)
            quote_api = upstox_client.MarketQuoteApi(api_client)

            response = quote_api.get_full_market_quote(
                symbol=instrument_key,
                api_version="v2",
            )

            # Response key format is "NSE_EQ:SYMBOL" not "NSE_EQ|ISIN"
            response_key = f"NSE_EQ:{symbol.upper()}"
            quote_data = response.data.get(response_key) if response.data else None

            if not quote_data:
                # Try with instrument_key as fallback
                quote_data = response.data.get(instrument_key) if response.data else None

            if not quote_data:
                raise ValueError(f"No quote data returned for {symbol}. Keys: {list(response.data.keys()) if response.data else []}")

            ltp = quote_data.last_price
            close = quote_data.ohlc.close if quote_data.ohlc else None
            net_change = getattr(quote_data, 'net_change', None)
            # SDK doesn't have percentage_change — compute from net_change and close
            if net_change is not None and close:
                pct_change = (net_change / close) * 100
            elif close and ltp:
                net_change = ltp - close
                pct_change = (net_change / close) * 100
            else:
                net_change = net_change or 0
                pct_change = 0

            return {
                "symbol": symbol,
                "ltp": ltp,
                "open": quote_data.ohlc.open if quote_data.ohlc else None,
                "high": quote_data.ohlc.high if quote_data.ohlc else None,
                "low": quote_data.ohlc.low if quote_data.ohlc else None,
                "close": close,
                "volume": getattr(quote_data, 'volume', None) or getattr(quote_data, 'volume_traded', None),
                "net_change": round(net_change, 4),
                "pct_change": round(pct_change, 2),
            }

        except ApiException as e:
            raise ValueError(f"Upstox API error for quote {symbol}: {e.status} - {e.reason}")
        except Exception as e:
            raise ValueError(f"Failed to fetch quote for {symbol}: {e}")

    async def get_index_quotes(self) -> list[dict]:
        """Get quotes for NIFTY 50, BANK NIFTY, SENSEX, and INDIA VIX."""
        await self._ensure_valid_token()
        if not self.access_token:
            return []

        instrument_keys = ",".join(self.INDEX_KEYS.values())

        try:
            api_client = upstox_client.ApiClient(self._configuration)
            quote_api = upstox_client.MarketQuoteApi(api_client)

            response = quote_api.get_full_market_quote(
                symbol=instrument_keys,
                api_version="v2",
            )

            results = []
            if response.data:
                for name, key in self.INDEX_KEYS.items():
                    # Response keys use colon separator: "NSE_INDEX:Nifty 50"
                    response_key = key.replace("|", ":")
                    quote = response.data.get(response_key)
                    if not quote:
                        continue

                    ltp = quote.last_price
                    close = quote.ohlc.close if quote.ohlc else ltp
                    raw_net_change = getattr(quote, 'net_change', None)
                    # Prefer API's net_change; fall back to ltp - close
                    if raw_net_change is not None:
                        change = raw_net_change
                    elif close and ltp:
                        change = ltp - close
                    else:
                        change = 0
                    change_pct = (change / close * 100) if close else 0

                    results.append({
                        "name": name,
                        "value": ltp,
                        "change": round(change, 2),
                        "changePct": round(change_pct, 2),
                    })

            return results

        except ApiException as e:
            logger.error(f"Upstox API error for index quotes: {e.status} - {e.reason}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch index quotes: {e}")
            return []

    # Market Status

    async def get_market_status_api(self) -> dict | None:
        """Get market status from Upstox API.

        Returns dict with 'exchange', 'status' (e.g. 'NormalOpen', 'Closed')
        or None if the API call fails.
        """
        await self._ensure_valid_token()
        if not self.access_token:
            return None

        try:
            api_client = upstox_client.ApiClient(self._configuration)
            market_api = upstox_client.MarketHolidaysAndTimingsApi(api_client)
            response = market_api.get_market_status(exchange="NSE")

            if response and response.data:
                return {
                    "exchange": getattr(response.data, 'exchange', 'NSE'),
                    "status": getattr(response.data, 'status', None),
                    "last_updated": getattr(response.data, 'last_updated', None),
                }
            return None
        except Exception as e:
            logger.warning(f"Upstox market status API failed: {e}")
            return None

    # Order Execution

    @staticmethod
    def _is_market_open() -> bool:
        """Check if NSE market is currently open (9:15 AM - 3:30 PM IST, weekdays, non-holidays)."""
        from datetime import timezone

        IST = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(IST)

        if now.weekday() >= 5:  # Weekend
            return False

        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return market_open <= now < market_close

    async def place_order(
        self,
        symbol: str,
        transaction_type: Literal["BUY", "SELL"],
        quantity: int,
        price: float,
        order_type: Literal["MARKET", "LIMIT"] = "LIMIT",
        is_amo: bool | None = None,
        product: Literal["D", "I"] = "D",
    ) -> TradeResult:
        """
        Place an order.

        In paper trading mode, simulates the order.
        In live mode, places a real order via Upstox SDK.

        Args:
            is_amo: Force AMO flag. If None, auto-detects based on market hours.
        """
        if self.paper_trading:
            return await self._paper_place_order(
                symbol, transaction_type, quantity, price, order_type, product
            )

        if not self.access_token:
            raise ValueError("Access token required for live trading")

        instrument_key = self._get_instrument_key(symbol)

        # Auto-detect AMO: if market is closed, send as after-market order
        if is_amo is None:
            is_amo = not self._is_market_open()

        try:
            api_client = upstox_client.ApiClient(self._configuration)
            order_api = upstox_client.OrderApiV3(api_client)

            body = upstox_client.PlaceOrderV3Request(
                quantity=quantity,
                product=product,
                validity="DAY",
                price=price if order_type == "LIMIT" else 0,
                trigger_price=0,  # No stop-loss trigger
                instrument_token=instrument_key,
                order_type=order_type,
                transaction_type=transaction_type,
                disclosed_quantity=0,  # Show full quantity (no iceberg)
                is_amo=is_amo,
            )

            response = order_api.place_order(body)

            # V3 API returns order_ids (list), not order_id
            order_ids = response.data.order_ids if response.data else []
            order_id = order_ids[0] if order_ids else None

            amo_label = " [AMO]" if is_amo else ""
            return TradeResult(
                success=True,
                order_id=order_id,
                status="PENDING",
                message=f"Order placed successfully{amo_label} (ID: {order_id})",
            )

        except ApiException as e:
            # Extract detailed error from response body
            detail = ""
            if e.body:
                try:
                    import json as _json
                    body = _json.loads(e.body) if isinstance(e.body, str) else e.body
                    detail = body.get("message", "") or body.get("errors", "")
                except Exception:
                    detail = str(e.body)[:200]
            msg = f"Order rejected: {e.status} - {e.reason}"
            if detail:
                msg += f" ({detail})"
            return TradeResult(
                success=False,
                status="REJECTED",
                message=msg,
            )
        except Exception as e:
            return TradeResult(
                success=False,
                status="REJECTED",
                message=f"Order failed: {e}",
            )

    async def _paper_place_order(
        self,
        symbol: str,
        transaction_type: Literal["BUY", "SELL"],
        quantity: int,
        price: float,
        order_type: Literal["MARKET", "LIMIT"],
        product: Literal["D", "I"] = "D",
    ) -> TradeResult:
        """Simulate order placement for paper trading with database persistence."""
        import random

        # Ensure portfolio is loaded from DB
        await self._ensure_portfolio_loaded()

        # Simulate execution with small slippage
        executed_price = price * (1 + random.uniform(-0.001, 0.001))
        order_id = f"PAPER_{self._paper_order_id}"
        self._paper_order_id += 1

        total_value = executed_price * quantity

        # Validate the trade before persisting
        if transaction_type == "BUY":
            if total_value > self._paper_portfolio.available_cash:
                return TradeResult(
                    success=False,
                    status="REJECTED",
                    message=f"Insufficient funds. Required: ₹{total_value:.2f}, Available: ₹{self._paper_portfolio.available_cash:.2f}",
                )
        else:  # SELL
            existing = next(
                (p for p in self._paper_portfolio.positions if p.symbol == symbol), None
            )
            if not existing or existing.quantity < quantity:
                return TradeResult(
                    success=False,
                    status="REJECTED",
                    message=f"Insufficient shares. Have: {existing.quantity if existing else 0}, Need: {quantity}",
                )

        # Save to database
        try:
            from services.trade_persistence import get_trade_persistence
            persistence = get_trade_persistence()

            if persistence:
                await persistence.save_trade(
                    user_id=self.user_id,
                    symbol=symbol,
                    direction=transaction_type,
                    quantity=quantity,
                    executed_price=executed_price,
                    order_type=order_type,
                    order_id=order_id,
                )
                logger.info(f"[UpstoxClient] Persisted paper trade to DB: {transaction_type} {quantity} {symbol}")

                # Reload portfolio from DB to reflect the new trade
                self._paper_portfolio = await persistence.get_portfolio_for_user(self.user_id)
            else:
                # Fallback: update in-memory portfolio (old behavior)
                logger.warning("[UpstoxClient] Trade persistence not available, updating in-memory only")
                self._update_portfolio_in_memory(symbol, transaction_type, quantity, executed_price)

        except Exception as e:
            logger.error(f"[UpstoxClient] Failed to persist trade: {e}")
            # Still update in-memory as fallback
            self._update_portfolio_in_memory(symbol, transaction_type, quantity, executed_price)

        return TradeResult(
            success=True,
            order_id=order_id,
            status="COMPLETE",
            executed_price=executed_price,
            executed_quantity=quantity,
            message=f"Paper trade executed: {transaction_type} {quantity} {symbol} @ ₹{executed_price:.2f}",
        )

    def _update_portfolio_in_memory(
        self,
        symbol: str,
        transaction_type: str,
        quantity: int,
        executed_price: float,
    ) -> None:
        """Update portfolio in memory (fallback when DB not available)."""
        total_value = executed_price * quantity

        if transaction_type == "BUY":
            self._paper_portfolio.available_cash -= total_value
            self._paper_portfolio.invested_value += total_value

            existing = next(
                (p for p in self._paper_portfolio.positions if p.symbol == symbol), None
            )
            if existing:
                total_qty = existing.quantity + quantity
                existing.average_price = (
                    existing.average_price * existing.quantity + executed_price * quantity
                ) / total_qty
                existing.quantity = total_qty
            else:
                self._paper_portfolio.positions.append(
                    PortfolioPosition(
                        symbol=symbol,
                        quantity=quantity,
                        average_price=executed_price,
                        current_price=executed_price,
                        pnl=0.0,
                        pnl_percentage=0.0,
                        day_change=0.0,
                        day_change_percentage=0.0,
                    )
                )

        else:  # SELL
            existing = next(
                (p for p in self._paper_portfolio.positions if p.symbol == symbol), None
            )
            if existing:
                pnl = (executed_price - existing.average_price) * quantity
                self._paper_portfolio.available_cash += total_value
                self._paper_portfolio.invested_value -= existing.average_price * quantity
                self._paper_portfolio.total_pnl += pnl

                existing.quantity -= quantity
                if existing.quantity == 0:
                    self._paper_portfolio.positions.remove(existing)

        self._paper_portfolio.total_value = (
            self._paper_portfolio.available_cash + self._paper_portfolio.invested_value
        )

    async def get_portfolio(self) -> Portfolio:
        """Get current portfolio."""
        if self.paper_trading:
            await self._ensure_portfolio_loaded()
            return self._paper_portfolio

        if not self.access_token:
            raise ValueError("No Upstox access token configured. Cannot fetch portfolio.")

        try:
            api_client = upstox_client.ApiClient(self._configuration)
            portfolio_api = upstox_client.PortfolioApi(api_client)

            response = portfolio_api.get_holdings(api_version="v2")
            holdings = response.data if response.data else []

            # Fetch today's positions to find delivery sells AND intraday positions.
            # Holdings API returns FULL quantity (pre-settlement). If the user
            # sold shares today, those appear as negative-qty delivery positions.
            # We must subtract them to match the actual portfolio.
            # Intraday (MIS) positions are collected separately.
            sell_qty_map: dict[str, int] = {}
            intraday_positions: list[PortfolioPosition] = []
            try:
                pos_response = portfolio_api.get_positions(api_version="v2")
                for pos in (pos_response.data or []):
                    qty = getattr(pos, 'quantity', 0) or 0
                    product = getattr(pos, 'product', '')
                    sym = (getattr(pos, 'tradingsymbol', None) or getattr(pos, 'trading_symbol', '') or '').upper()

                    if product == 'D' and qty < 0:
                        # Delivery sell today — subtract from holdings
                        if sym:
                            sell_qty_map[sym] = sell_qty_map.get(sym, 0) + abs(qty)
                    elif product == 'I' and qty != 0:
                        # Intraday (MIS) position — collect it
                        if sym:
                            # Cache instrument_token for chart/quote lookups
                            inst_token = getattr(pos, 'instrument_token', None)
                            if inst_token:
                                self._dynamic_symbols[sym] = inst_token

                            avg_price = getattr(pos, 'average_price', 0) or getattr(pos, 'buy_price', 0) or 0
                            last_price = getattr(pos, 'last_price', 0) or 0
                            close_price = getattr(pos, 'close_price', 0) or 0

                            if avg_price and last_price:
                                intra_pnl = (last_price - avg_price) * qty
                                intra_pnl_pct = ((last_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
                            else:
                                intra_pnl = 0.0
                                intra_pnl_pct = 0.0

                            if close_price and last_price:
                                intra_day_chg = last_price - close_price
                                intra_day_chg_pct = (intra_day_chg / close_price * 100)
                            else:
                                intra_day_chg = 0.0
                                intra_day_chg_pct = 0.0

                            intraday_positions.append(
                                PortfolioPosition(
                                    symbol=sym,
                                    quantity=abs(qty),
                                    average_price=avg_price,
                                    current_price=last_price,
                                    pnl=intra_pnl,
                                    pnl_percentage=intra_pnl_pct,
                                    day_change=intra_day_chg,
                                    day_change_percentage=intra_day_chg_pct,
                                    product='I',
                                )
                            )
            except Exception as e:
                logger.warning(f"Failed to fetch positions: {e}")

            positions = []
            for holding in holdings:
                # Cache instrument_token so chart/quote can look up any holding
                tsym = holding.tradingsymbol or holding.trading_symbol
                inst_token = getattr(holding, 'instrument_token', None)
                if tsym and inst_token:
                    self._dynamic_symbols[tsym.upper()] = inst_token

                # Adjust quantity for today's sells (unsettled T+1)
                adj_qty = holding.quantity - sell_qty_map.get(tsym.upper(), 0)
                if adj_qty <= 0:
                    continue  # Fully sold today, skip

                # Upstox day_change/day_change_percentage are unreliable:
                # Always compute from close_price (prev session close) and last_price.
                close_price = getattr(holding, 'close_price', None) or 0
                last_price = holding.last_price or 0

                if close_price and last_price:
                    day_chg = last_price - close_price  # per-share
                    day_chg_pct = (day_chg / close_price * 100)
                else:
                    day_chg = 0.0
                    day_chg_pct = 0.0

                # Recalculate P&L based on adjusted quantity
                pnl = (last_price - holding.average_price) * adj_qty
                pnl_pct = ((last_price - holding.average_price) / holding.average_price * 100) if holding.average_price > 0 else 0

                positions.append(
                    PortfolioPosition(
                        symbol=tsym,
                        quantity=adj_qty,
                        average_price=holding.average_price,
                        current_price=last_price,
                        pnl=pnl,
                        pnl_percentage=pnl_pct,
                        day_change=day_chg,
                        day_change_percentage=day_chg_pct,
                        product='D',
                    )
                )

            invested = sum(p.average_price * p.quantity for p in positions)
            current = sum(p.current_price * p.quantity for p in positions)
            day_pnl = sum(p.day_change * p.quantity for p in positions)
            total_pnl = current - invested
            # Previous close total = current value minus today's change
            prev_close_total = current - day_pnl

            # Fetch available cash from funds API (unavailable 12:00 AM - 5:30 AM IST)
            available_cash = 0.0
            try:
                user_api = upstox_client.UserApi(api_client)
                funds_response = user_api.get_user_fund_margin(api_version="v2")
                if funds_response.data:
                    equity_data = funds_response.data.get("equity")
                    if equity_data:
                        available_cash = equity_data.available_margin or 0.0
                if available_cash > 0:
                    self._cache_available_cash(available_cash)
            except Exception as e:
                logger.warning(f"Failed to fetch funds/margin: {e}")

            # Fall back to cached value when funds API is unavailable
            if available_cash == 0:
                available_cash = self._read_cached_available_cash()

            return Portfolio(
                total_value=current + available_cash,
                available_cash=available_cash,
                invested_value=invested,
                day_pnl=day_pnl,
                day_pnl_percentage=(day_pnl / prev_close_total * 100) if prev_close_total else 0,
                total_pnl=total_pnl,
                total_pnl_percentage=(total_pnl / invested * 100) if invested > 0 else 0,
                positions=positions,
                intraday_positions=intraday_positions,
            )

        except ApiException as e:
            raise ValueError(f"Failed to fetch portfolio: {e.status} - {e.reason}. {e.body}")
        except Exception as e:
            raise ValueError(f"Failed to fetch portfolio: {e}")

    def _cash_cache_path(self) -> Path:
        """Path for the per-user available cash cache file."""
        cache_dir = Path(__file__).resolve().parent.parent / ".cache"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir / f"funds_user_{self.user_id}.json"

    def _cache_available_cash(self, amount: float) -> None:
        """Persist available cash to file for offline fallback."""
        try:
            self._cash_cache_path().write_text(json.dumps({"available_cash": amount}))
        except Exception as e:
            logger.warning(f"Failed to write cash cache: {e}")

    def _read_cached_available_cash(self) -> float:
        """Read cached available cash from file."""
        try:
            data = json.loads(self._cash_cache_path().read_text())
            return data.get("available_cash", 0.0)
        except Exception:
            return 0.0

    def get_known_symbols(self) -> list[str]:
        """Get list of supported stock symbols (all NSE symbols if cache available)."""
        from services.instruments_cache import get_all_symbols, ensure_loaded
        ensure_loaded()
        all_syms = get_all_symbols()
        if all_syms:
            return all_syms
        return sorted(self.SYMBOL_TO_ISIN.keys())

    async def get_orders(self) -> list[dict]:
        """
        Get all orders for the current day.

        Returns:
            List of order dictionaries with order details
        """
        if self.paper_trading:
            # Return empty list for paper trading (orders are executed immediately)
            return []

        if not self.access_token:
            raise ValueError("No Upstox access token configured. Cannot fetch orders.")

        try:
            api_client = upstox_client.ApiClient(self._configuration)
            # Order book is on v2 OrderApi, not OrderApiV3
            order_api = upstox_client.OrderApi(api_client)

            response = order_api.get_order_book(api_version="v2")
            orders_data = response.data if response.data else []

            orders = []
            for order in orders_data:
                orders.append({
                    "order_id": order.order_id,
                    "symbol": order.tradingsymbol,
                    "transaction_type": order.transaction_type,
                    "quantity": order.quantity,
                    "order_type": order.order_type,
                    "price": order.price,
                    "average_price": getattr(order, 'average_price', None),
                    "status": order.status,
                    "timestamp": getattr(order, 'order_timestamp', None),
                })

            return orders

        except ApiException as e:
            raise ValueError(f"Failed to fetch orders: {e.status} - {e.reason}")
        except Exception as e:
            raise ValueError(f"Failed to fetch orders: {e}")

    async def cancel_order(self, order_id: str) -> dict:
        """
        Cancel an open order.

        Args:
            order_id: The order ID to cancel

        Returns:
            Dict with success status and message
        """
        if self.paper_trading:
            # Paper trading orders execute immediately, can't cancel
            return {
                "success": False,
                "message": "Paper trading orders are executed immediately and cannot be cancelled."
            }

        if not self.access_token:
            raise ValueError("No Upstox access token configured. Cannot cancel order.")

        try:
            api_client = upstox_client.ApiClient(self._configuration)
            order_api = upstox_client.OrderApiV3(api_client)

            response = order_api.cancel_order(order_id=order_id)

            return {
                "success": True,
                "message": f"Order {order_id} cancelled successfully"
            }

        except ApiException as e:
            return {
                "success": False,
                "message": f"Failed to cancel order: {e.status} - {e.reason}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to cancel order: {e}"
            }
