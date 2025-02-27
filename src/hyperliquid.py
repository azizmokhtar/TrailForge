import ccxt
import ccxt
import time 
import pandas as pd
from datetime import datetime

walletAdress = "0x673Aa1aF74F2436BCbA24DC2A80089B77A3D10e8"
privateKey = "0xe4ac2035a8ac1052cc93e92592398bd4644ef7cec1352126543c0fa6a806e4aa"


class hyperLiquid:
    def __init__(self, wallet_address, private_key):
        self.wallet_address = "0x673Aa1aF74F2436BCbA24DC2A80089B77A3D10e8"
        self.private_key = "0xe4ac2035a8ac1052cc93e92592398bd4644ef7cec1352126543c0fa6a806e4aa"
        self.exchange = ccxt.hyperliquid({
            "walletAddress": wallet_address,
            "privateKey": private_key,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
            },
        })

    @classmethod
    async def create(cls, x= "0x673Aa1aF74F2436BCbA24DC2A80089B77A3D10e8", private_key = "0xe4ac2035a8ac1052cc93e92592398bd4644ef7cec1352126543c0fa6a806e4aa"):
        instance = cls(x, private_key)
        return instance

    async def fetchTicker(self, symbol):
        try:
            data = self.exchange.fetch_ticker(symbol)
            return {
                "bid": data["bid"],
                "ask": data["ask"],
                "last": data["last"]
            }
        except Exception as e:
            print(f"Error fetching ticker: {e}")
            return None
 
    #===============================================================================================================
    # Market data 
    #===============================================================================================================
        # This is to be work done (for better usability, still raw)
    async def fetchBalance(self):
        try:
            balance = self.exchange.fetch_balance(params={'user': self.wallet_adress})
            # Extracting valuable information
            account_value = float(balance['info']['marginSummary']['accountValue'])
            total_margin_used = float(balance['info']['marginSummary']['totalMarginUsed'])
            withdrawable = float(balance['info']['withdrawable'])
            usdc_total = balance['USDC']['total']
            usdc_free = balance['USDC']['free']
            usdc_used = balance['USDC']['used']
            timestamp = balance['datetime']
            return timestamp, account_value, total_margin_used, withdrawable, usdc_total, usdc_free, usdc_used
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return None

    async def fetchMarkets(self):
        try:
            data = self.exchange.fetch_markets()
            df = pd.DataFrame(data)
            # Step 2: Extract spot and linear symbols
            spot_symbols = [
                row['symbol'] 
                for _, row in df.iterrows() 
                if row['type'] == 'spot' and row.get('spot') is True
            ]
            linear_symbols = [
                row['symbol'] 
                for _, row in df.iterrows() 
                if row['type'] == 'swap' and row.get('linear') is True
            ]
            # Step 3: Ensure both lists have the same length by padding with None
            max_length = max(len(spot_symbols), len(linear_symbols))
            spot_symbols_padded = spot_symbols + [None] * (max_length - len(spot_symbols))
            linear_symbols_padded = linear_symbols + [None] * (max_length - len(linear_symbols))
            # Step 4: Create a DataFrame with two columns
            df = pd.DataFrame({
                'Spot Symbols': spot_symbols_padded,
                'Linear Symbols': linear_symbols_padded
            })
            # Step 5: Save the DataFrame to a CSV file
            output_file = 'symbols.csv'
            df.to_csv(output_file, index=False)
        except Exception as e:
            print(f"Error fetching markets: {e}")

    async def fetchOHLCVData(self, symbol, timeframe, ticks):
        try:
            print(f"Fetching new bars for {datetime.now().isoformat()}")
            bars = self.exchange.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=(ticks+1))  # limit is the number of ticks
            df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            print(df)
        except Exception as e:
            print(f"Error fetching OHLCV data: {e}")


    async def fetchTicker(self, symbol):
        try:
            data = self.exchange.fetch_ticker(symbol)
            return {
                "bid": data["bid"],
                "ask": data["ask"],
                "last": data["last"]
            }
        except Exception as e:
            print(f"Error fetching ticker: {e}")
            return None
    
    #===============================================================================================================
    # Account manips 
    #===============================================================================================================

    async def setLeverage(self, leverage, symbol):
        try:
            self.exchange.set_leverage(leverage=leverage, symbol=symbol)
            print("Leverage set")
        except Exception as e:
            print(f"Error setting leverage: {e}")

    async def leveragedMarketOrder(self, symbol, side, amount, price):
        try:
            if side == 'Buy':
                amount_in_quote = amount / price
                order = self.exchange.create_market_order(symbol=symbol, side=side, amount=amount_in_quote, price=price)
                buy_price = order['info']['filled']['avgPx']
                order_id = order['info']['filled']['oid']
            elif side == 'Sell':
                amount_in_quote = amount / price
                order = self.exchange.create_market_order(symbol=symbol, side=side, amount=amount, price=price, params={'reduceOnly': True})
                buy_price = order['info']['filled']['avgPx']
                order_id = order['info']['filled']['oid']
            return buy_price, order_id
        except Exception as e:
            print(f"Error placing leveraged market order: {e}")
            return None, None

    async def closeAllPositions(self, symbol, side, amount, price):
        try:
            amount_in_quote = amount / price
            order = self.exchange.create_market_order(symbol=symbol, side=side, amount=amount_in_quote, price=price)
            buy_price = order['info']['filled']['avgPx']
            order_id = order['info']['filled']['oid']
            return buy_price, order_id
        except Exception as e:
            print(f"Error closing all positions: {e}")
            return None, None

    # ONLY when 1 ticker traded
    async def fetchOpenOrders(self):
        try:
            positions = self.exchange.fetch_positions()
            if positions == []:
                print("No open positions found")
                return None
            else:
                position_info = positions[0]['info']['position']
                szi = float(position_info['szi'])
                entry_px = float(position_info['entryPx'])
                position_value = float(position_info['positionValue'])
                unrealizedPnl = float(position_info['returnOnEquity'])
                return entry_px, position_value, szi, unrealizedPnl
        except Exception as e:
            print(f"Error fetching open orders: {e}")
            return None

    async def leverageLimitOrder(self, symbol, side, amount, price):
        try:
            amount_in_quote = amount / price
            order = self.exchange.create_limit_order(symbol=symbol, side=side, amount=amount_in_quote, price=price, params={'reduceOnly': True})
            order_id = order['info']['resting']['oid']
            return order_id
        except Exception as e:
            print(f"Error placing leveraged limit order: {e}")
            return None

    # This is the one used for now its good
    async def leverageLimitBuyOrder(self, symbol, side, amount, price):
        try:
            amount_in_quote = amount / price
            order = self.exchange.create_limit_order(symbol=symbol, side=side, amount=amount_in_quote, price=price)
            order_id = order['info']['resting']['oid']
            return order_id
        except Exception as e:
            print(f"Error placing leveraged limit buy order: {e}")
            return None



    async def updateLimitOrders(self, id, symbol, side, amount, price):
        try:
            self.exchange.cancel_order(id=id, symbol=symbol)
            order_id = self.leverageLimitOrder(symbol, side=side, amount=amount, price=price, params={'reduceOnly': True})
            return order_id
        except Exception as e:
            print(f"Error updating limit orders: {e}")
            return None

    #===============================================================================================================
    # Utils
    #===============================================================================================================

    async def calculateNextDca(self, price, deviation):
        try:
            return price * (1 - (deviation / 100))
        except Exception as e:
            print(f"Error calculating next DCA: {e}")
            return None
    
    async def calculateTp(self, price, tp):
        try:
            return price * (1 + (tp / 100))
        except Exception as e:
            print(f"Error calculating take profit: {e}")
            return None
    
