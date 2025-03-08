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

    