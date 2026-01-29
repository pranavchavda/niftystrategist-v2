"""Upstox API client using the official SDK."""

import logging
import os
from datetime import datetime, timedelta
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
        """Get the instrument key for a symbol."""
        isin = self.SYMBOL_TO_ISIN.get(symbol.upper())
        if not isin:
            raise ValueError(
                f"No ISIN mapping for symbol '{symbol}'. "
                f"Known symbols: {', '.join(sorted(self.SYMBOL_TO_ISIN.keys()))}"
            )
        return f"NSE_EQ|{isin}"

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
        if not self.access_token:
            raise ValueError(
                f"No Upstox access token configured. Cannot fetch data for {symbol}. "
                "Complete OAuth flow first."
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

            response = history_api.get_historical_candle_data(
                instrument_key=instrument_key,
                unit=unit,
                interval=interval_value,
                to_date=to_date,
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
        if not self.access_token:
            raise ValueError(f"No Upstox access token configured. Cannot fetch quote for {symbol}.")

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

            return {
                "symbol": symbol,
                "ltp": quote_data.last_price,
                "open": quote_data.ohlc.open if quote_data.ohlc else None,
                "high": quote_data.ohlc.high if quote_data.ohlc else None,
                "low": quote_data.ohlc.low if quote_data.ohlc else None,
                "close": quote_data.ohlc.close if quote_data.ohlc else None,
                "volume": getattr(quote_data, 'volume', None) or getattr(quote_data, 'volume_traded', None),
            }

        except ApiException as e:
            raise ValueError(f"Upstox API error for quote {symbol}: {e.status} - {e.reason}")
        except Exception as e:
            raise ValueError(f"Failed to fetch quote for {symbol}: {e}")

    # Order Execution

    async def place_order(
        self,
        symbol: str,
        transaction_type: Literal["BUY", "SELL"],
        quantity: int,
        price: float,
        order_type: Literal["MARKET", "LIMIT"] = "LIMIT",
    ) -> TradeResult:
        """
        Place an order.

        In paper trading mode, simulates the order.
        In live mode, places a real order via Upstox SDK.
        """
        if self.paper_trading:
            return await self._paper_place_order(
                symbol, transaction_type, quantity, price, order_type
            )

        if not self.access_token:
            raise ValueError("Access token required for live trading")

        instrument_key = self._get_instrument_key(symbol)

        try:
            api_client = upstox_client.ApiClient(self._configuration)
            order_api = upstox_client.OrderApiV3(api_client)

            body = upstox_client.PlaceOrderV3Request(
                quantity=quantity,
                product="D",  # Delivery
                validity="DAY",
                price=price if order_type == "LIMIT" else 0,
                trigger_price=0,  # No stop-loss trigger
                instrument_token=instrument_key,
                order_type=order_type,
                transaction_type=transaction_type,
                disclosed_quantity=0,  # Show full quantity (no iceberg)
                is_amo=False,  # Not after-market order
            )

            response = order_api.place_order(body)

            return TradeResult(
                success=True,
                order_id=response.data.order_id if response.data else None,
                status="PENDING",
                message="Order placed successfully",
            )

        except ApiException as e:
            return TradeResult(
                success=False,
                status="REJECTED",
                message=f"Order rejected: {e.status} - {e.reason}",
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

            response = portfolio_api.get_holdings()
            holdings = response.data if response.data else []

            positions = []
            for holding in holdings:
                positions.append(
                    PortfolioPosition(
                        symbol=holding.tradingsymbol,
                        quantity=holding.quantity,
                        average_price=holding.average_price,
                        current_price=holding.last_price,
                        pnl=holding.pnl,
                        pnl_percentage=(holding.pnl / (holding.average_price * holding.quantity)) * 100 if holding.quantity > 0 else 0,
                        day_change=getattr(holding, 'day_change', 0) or 0,
                        day_change_percentage=getattr(holding, 'day_change_percentage', 0) or 0,
                    )
                )

            invested = sum(p.average_price * p.quantity for p in positions)
            current = sum(p.current_price * p.quantity for p in positions)

            return Portfolio(
                total_value=current,
                available_cash=0,  # Would need funds API
                invested_value=invested,
                day_pnl=sum(p.day_change * p.quantity for p in positions),
                day_pnl_percentage=0,
                total_pnl=current - invested,
                total_pnl_percentage=((current - invested) / invested * 100) if invested > 0 else 0,
                positions=positions,
            )

        except ApiException as e:
            raise ValueError(f"Failed to fetch portfolio: {e.status} - {e.reason}. {e.body}")
        except Exception as e:
            raise ValueError(f"Failed to fetch portfolio: {e}")

    def get_known_symbols(self) -> list[str]:
        """Get list of supported stock symbols."""
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
            order_api = upstox_client.OrderApiV3(api_client)

            response = order_api.get_order_book()
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
