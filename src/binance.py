import ccxt
import time
import pandas as pd
from datetime import datetime
import asyncio
from sandLayerAnalyzer  import sandLayerAnalyzer
class binanceFutures:
    #===============================================================================================================
    # Bot Initialization, will ask for keys and address as input (works only for hyperliquid format for now)
    #===============================================================================================================
    def __init__(self, wallet_address, private_key):
        # Initialize the exchange connection with provided keys
        self.exchange = ccxt.binance({
            'apiKey': 'YOUR_API_KEY',
            'secret': 'YOUR_SECRET',
            'options': {
                'defaultType': 'future',
            },
        })

    @classmethod
    async def create(cls, apiKey=None, private_key=None):
        """
        Create an instance of the HyperLiquid class.
        If wallet_address or private_key are not provided, prompt the user for input.
        """
        if not apiKey or not secret:
            wallet_address, secret = cls.get_user_credentials()
            
        # Create and return an instance of the class
        return cls(apiKey, secret)

    @staticmethod
    def get_user_credentials():
        """
        Prompt the user to input their wallet address and private key.
        Returns:
        tuple: (wallet_address, private_key)
        """
        while True:
            apiKey = input("Enter your wallet address (e.g., 0x...): ").strip()
            if apiKey.startswith("0x") and len(apiKey) == 42:
                break
            print("Invalid wallet address format. It must be a 42-character Ethereum address starting with '0x'.")
            
        while True:
            secret = input("Enter your private key (e.g., 0x...): ").strip()
            if secret.startswith("0x") and len(secret) == 66:
                break
            print("Invalid private key format. It must be a 66-character string starting with '0x'.")
            
        return apiKey, secret
    
 
    #===============================================================================================================
    # READ functions for according exchange account 
    #===============================================================================================================

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
    
    #===============================================================================================================
    # MANIPULATION functions for according exchange account (for now only futures is taken into consideration, future changes coming)
    # TODO: + check_order_status function for order failure 
    #       + add post only/ limit order fonctionality for something other than TV alerts, since they need urgent execution.. unless my pinescipts plots tp and dca levels
    #===============================================================================================================
    
    async def setLeverage(self, leverage, symbol):
        try:
            self.exchange.set_leverage(leverage=leverage, symbol=symbol)
            print("Leverage set")
        except Exception as e:
            print(f"Error setting leverage: {e}")

    async def leveragedMarketOrder(self, symbol, side, amount):
        try:
            # Fetch the current price for the symbol
            ticker_data = await self.fetchTicker(symbol) #  
            if not ticker_data:
                print("Failed to fetch ticker data for placing a market order!")
                return None, None

            price = ticker_data["ask"] if side.lower() == "buy" else ticker_data["bid"]
            # Calculate the amount (in base asset) to achieve the desired order value
            amount_in_base = amount / price
            # Place the market order
            order =  self.exchange.create_market_order(
                symbol=symbol,
                side=side.lower(),
                amount=amount_in_base,
                price=price,
            )
            # Extract relevant information from the order response
            buy_price = order['info']['filled']['avgPx']
            order_id = order['info']['filled']['oid']

            return buy_price, order_id
        except Exception as e:
            print(f"Error placing leveraged market {side} order: {e}")
            return None, None
        
    async def leveragedMarketCloseOrder(self, symbol, side_to_close, amount):
        try:
            # Fetch the current price for the symbol
            ticker_data = await self.fetchTicker(symbol) # DO NOT USE AWAIT WITH CCCXT REST SORDERS 
            if not ticker_data:
                print("Failed to fetch ticker data for closing a market order!")
                return None, None

            price = ticker_data["ask"] if side_to_close.lower() == "buy" else ticker_data["bid"]
            # Calculate the amount (in base asset) to achieve the desired order value
            amount_in_base = amount / price
            # Place the market order
            order =  self.exchange.create_market_order(
                symbol=symbol,
                side="sell" if side_to_close.lower()== "buy" else "buy",
                amount=amount_in_base,
                price=price,
                params={'reduceOnly': True}
            )
            # Extract relevant information from the order response
            buy_price = order['info']['filled']['avgPx']
            order_id = order['info']['filled']['oid']

            return buy_price, order_id
        except Exception as e:
            print(f"Error placing leveraged market close order: {e}")
            return None, None

    async def createLimitBuyOrders(self, symbol, prices, amount):
        try:
            for i in prices:
                amount_in_base = amount / i
                self.exchange.create_limit_buy_order(symbol, amount_in_base, i)
            return 1

        except Exception as e:
            print(f"Error placing leveraged limit DCA orders: {e}")
            return 0

    async def cancelLimitOrders(self, symbol):
        try:
            cancelled_order = self.exchange.cancel_all_orders(symbol)
            return cancelled_order
        
        except Exception as e:
            print(f"Error cancelling limit orders: {e}")
            return None