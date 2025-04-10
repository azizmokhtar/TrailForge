


import ccxt
import time
import pandas as pd
from datetime import datetime
import asyncio

class hyperLiquid:
    #===============================================================================================================
    # Bot Initialization, will ask for keys and address as input (works only for hyperliquid format for now)
    #===============================================================================================================
    def __init__(self, wallet_address, private_key):
        # Initialize the exchange connection with provided keys
        self.exchange = ccxt.hyperliquid({
            "walletAddress": wallet_address,
            "privateKey": private_key,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
            },
        })

    @classmethod
    async def create(cls, wallet_address=None, private_key=None):
        """
        Create an instance of the HyperLiquid class.
        If wallet_address or private_key are not provided, prompt the user for input.
        """
        if not wallet_address or not private_key:
            wallet_address, private_key = cls.get_user_credentials()
            
        # Create and return an instance of the class
        return cls(wallet_address, private_key)

    @staticmethod
    def get_user_credentials():
        """
        Prompt the user to input their wallet address and private key.
        Returns:
        tuple: (wallet_address, private_key)
        """
        while True:
            wallet_address = input("Enter your wallet address (e.g., 0x...): ").strip()
            if wallet_address.startswith("0x") and len(wallet_address) == 42:
                break
            print("Invalid wallet address format. It must be a 42-character Ethereum address starting with '0x'.")
            
        while True:
            private_key = input("Enter your private key (e.g., 0x...): ").strip()
            if private_key.startswith("0x") and len(private_key) == 66:
                break
            print("Invalid private key format. It must be a 66-character string starting with '0x'.")
            
        return wallet_address, private_key

#===============================================================================================================
# READ functions for according exchange account 
#===============================================================================================================
    # This is to be work done (for better usability, still raw)
    def fetchBalance(self):
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

    def fetchMarkets(self):
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

    def fetchOHLCVData(self, symbol, timeframe, ticks):
        try:
            print(f"Fetching new bars for {datetime.now().isoformat()}")
            bars = self.exchange.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=(ticks+1))  # limit is the number of ticks
            df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            print(df)
        except Exception as e:
            print(f"Error fetching OHLCV data: {e}")

    def fetchTicker(self, symbol):
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
# MANIPULATION functions for according exchange account
#===============================================================================================================
    def setLeverage(self, leverage, symbol):
        try:
            self.exchange.set_leverage(leverage=leverage, symbol=symbol)
            print("Leverage set")
        except Exception as e:
            print(f"Error setting leverage: {e}")
    # For now this is the used function for opening orders and closing ( will have to change the closing to close side instead of just "sell")
    def leveragedMarketOrder(self, symbol, side, amount):
        try:
            # Fetch the current price for the symbol
            ticker_data = self.fetchTicker(symbol)
            if not ticker_data:
                print("Failed to fetch ticker data.")
                return None, None

            price = ticker_data["ask"] if side == "Buy" else ticker_data["bid"]
            # Calculate the amount (in base asset) to achieve the desired order value
            amount_in_base = amount / price
            # Place the market order
            order = self.exchange.create_market_order(
                symbol=symbol,
                side=side.lower(),
                amount=amount_in_base,
                price=price,
                params={'reduceOnly': True} if side == "Sell" else {}
            )
            # Extract relevant information from the order response
            buy_price = order['info']['filled']['avgPx']
            order_id = order['info']['filled']['oid']

            return buy_price, order_id
        except Exception as e:
            print(f"Error placing leveraged market order: {e}")
            return None, None

    def closeAllPositions(self, symbol, side, amount, price):
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
    def fetchOpenOrders(self):
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

    def leverageLimitOrder(self, symbol, side, amount, price):
        try:
            amount_in_quote = amount / price
            order = self.exchange.create_limit_order(symbol=symbol, side=side, amount=amount_in_quote, price=price, params={'reduceOnly': True})
            order_id = order['info']['resting']['oid']
            return order_id
        except Exception as e:
            print(f"Error placing leveraged limit order: {e}")
            return None
    # This is the one used for now its good
    def leverageLimitBuyOrder(self, symbol, side, amount, price):
        try:
            amount_in_quote = amount / price
            order = self.exchange.create_limit_order(symbol=symbol, side=side, amount=amount_in_quote, price=price)
            order_id = order['info']['resting']['oid']
            return order_id
        except Exception as e:
            print(f"Error placing leveraged limit buy order: {e}")
            return None



    def updateLimitOrders(self, id, symbol, side, amount, price):
        try:
            self.exchange.cancel_order(id=id, symbol=symbol)
            order_id = self.leverageLimitOrder(symbol, side=side, amount=amount, price=price, params={'reduceOnly': True})
            return order_id
        except Exception as e:
            print(f"Error updating limit orders: {e}")
            return None

#===============================================================================================================
# random Utils
#===============================================================================================================

    def calculateNextDca(self, price, deviation):
        try:
            return price * (1 - (deviation / 100))
        except Exception as e:
            print(f"Error calculating next DCA: {e}")
            return None
    
    def calculateTp(self, price, tp):
        try:
            return price * (1 + (tp / 100))
        except Exception as e:
            print(f"Error calculating take profit: {e}")
            return None


class hyperLiquidSpot:
    #===============================================================================================================
    # Bot Initialization, will ask for keys and address as input (works only for hyperliquid format for now)
    #===============================================================================================================
    def __init__(self, wallet_address, private_key):
        # Initialize the exchange connection with provided keys
        self.exchange = ccxt.hyperliquid({
            "walletAddress": wallet_address,
            "privateKey": private_key,
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot",
            },
        })

    @classmethod
    def create(cls, wallet_address=None, private_key=None):
        """
        Create an instance of the HyperLiquid class.
        If wallet_address or private_key are not provided, prompt the user for input.
        """
        if not wallet_address or not private_key:
            wallet_address, private_key = cls.get_user_credentials()
            
        # Create and return an instance of the class
        return cls(wallet_address, private_key)

    @staticmethod
    def get_user_credentials():
        """
        Prompt the user to input their wallet address and private key.
        Returns:
        tuple: (wallet_address, private_key)
        """
        while True:
            wallet_address = input("Enter your wallet address (e.g., 0x...): ").strip()
            if wallet_address.startswith("0x") and len(wallet_address) == 42:
                break
            print("Invalid wallet address format. It must be a 42-character Ethereum address starting with '0x'.")
            
        while True:
            private_key = input("Enter your private key (e.g., 0x...): ").strip()
            if private_key.startswith("0x") and len(private_key) == 66:
                break
            print("Invalid private key format. It must be a 66-character string starting with '0x'.")
            
        return wallet_address, private_key
    
    def fetchTicker(self, symbol):
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
    
    def marketSpotOrder(self, symbol, quote_amount=15):

        try:
            # Get current market price
            ticker = self.fetchTicker(symbol)
            if not ticker:
                print(f"Failed to fetch ticker for {symbol}")
                return None

            # Calculate the amount in base currency
            price = ticker["last"]  # Using the last price
            amount_in_base = quote_amount / price

            # Place the market buy order
            order = self.exchange.create_market_buy_order(symbol=symbol, amount=amount_in_base, price=price)
            print(f"Market buy order placed: {amount_in_base} {symbol.split('/')[0]} at approximately {price}")
            return order

        except Exception as e:
            print(f"Error placing market buy order: {e}")
            return None




bot = hyperLiquidSpot.create()
symbol = "HYPE/USDC"
order = bot.marketSpotOrder(symbol=symbol, quote_amount=12)



