import os
import json
import time
import polars as pl
import asyncio
from datetime import datetime, timedelta

class truthCompass:
    def __init__(self, symbol, ttl=30*86400):
        """Initialize truthCompass with data directory and TTL in seconds."""
        # Make sure logs directory exists
        os.makedirs("logs", exist_ok=True)
        self.symbol = symbol
        self.default_ttl = ttl
        
        # Get file paths
        self.dsrFilePath, self.rawFilePath = self._get_filepath(symbol)
        
        # Define schema with explicit types to prevent type mismatches
        self.schema = {
            "timestamp": pl.Datetime,
            "symbol": pl.Utf8,
            "side": pl.Utf8,
            "price": pl.Float64,
            "cycleBuy": pl.Int64,
        }
        
        # Initialize dataframes as None - they'll be loaded asynchronously
        self.rawFile = None
        self.dsrFile = None
    
    def _get_filepath(self, symbol):
        """Generate filepath for storing order history."""
        dsrFile = f"logs/dsr_{symbol.lower()}_signal.parquet"
        rawFile = f"logs/raw_{symbol.lower()}_signal.parquet"
        return dsrFile, rawFile
    
    async def _load_data(self):
        """Load data asynchronously on first use"""
        if self.rawFile is None:
            if os.path.exists(self.rawFilePath):
                self.rawFile = await asyncio.to_thread(pl.read_parquet, self.rawFilePath)
            else:
                self.rawFile = pl.DataFrame(
                    {
                        "timestamp": [],
                        "symbol": [],
                        "side": [],
                        "price": [],
                        "cycleBuy": [],
                    },
                    schema=self.schema
                )
                
        if self.dsrFile is None:
            if os.path.exists(self.dsrFilePath):
                self.dsrFile = await asyncio.to_thread(pl.read_parquet, self.dsrFilePath)
            else:
                self.dsrFile = pl.DataFrame(
                    {
                        "timestamp": [],
                        "symbol": [],
                        "side": [],
                        "price": [],
                        "cycleBuy": [],
                    },
                    schema=self.schema
                )
    
    async def save(self):
        """Save dataframes to disk asynchronously."""
        await self._load_data()
        
        # Run Polars write operations in thread pool
        await asyncio.gather(
            asyncio.to_thread(self.rawFile.write_parquet, self.rawFilePath),
            asyncio.to_thread(self.dsrFile.write_parquet, self.dsrFilePath)
        )
    
    async def checkAndUpdate(self, symbol, side, price, cycleBuy):
        """
        Update the signal in the timed list and return status asynchronously.
        
        Args:
            symbol (str): Trading symbol
            side (str): 'buy' or 'sell'
            price (float): Trade price
            cycleBuy (int or str): Cycle buy number
            
        Returns:
            int: 0 if signal is new, 1 if it already exists
        """
        await self._load_data()
        
        # Convert inputs to appropriate types for comparison
        price = float(price)
        cycleBuy = int(cycleBuy)
        side = str(side)
        
        # Remove expired signals (older than TTL)
        if not await asyncio.to_thread(lambda: self.rawFile.is_empty()):
            # Convert timestamp strings to epoch time for comparison
            expiration_datetime = datetime.now() - timedelta(seconds=self.default_ttl)

            # Filter using datetime comparison (run in thread pool)
            self.rawFile = await asyncio.to_thread(
                lambda: self.rawFile.filter(pl.col("timestamp") > expiration_datetime)
            )
                    
        # Check if signal exists in DSR file
        if not await asyncio.to_thread(lambda: self.dsrFile.is_empty()):
            time_window = datetime.now() - timedelta(minutes=2)
            matches = await asyncio.to_thread(
                lambda: self.dsrFile.filter(
                    (pl.col("timestamp") > time_window)
                    (pl.col("symbol") == symbol) & 
                    (pl.col("side") == side) & 
                    (pl.col("cycleBuy") == cycleBuy)
                )
            )
            
            if await asyncio.to_thread(lambda: matches.height > 0):
                # Signal already exists in DSR
                return 1
            
        await self.addNewSignal("dsr", symbol, side, price, cycleBuy)

        # Save changes
        await self.save()
        return 0
    
    async def addNewSignal(self, type, symbol, side, price, cycleBuy):
        """
        Add a new signal to either the raw or DSR file asynchronously.

        Args:
            type (str): "raw" or "dsr" to specify which file to add to
            symbol (str): Trading symbol
            side (str): 'buy' or 'sell'
            price (float): Trade price
            cycleBuy (int): Cycle buy number
        """
        try:
            await self._load_data()
            timestamp = datetime.now()
    
            price = float(price)
            cycleBuy = int(cycleBuy)
            side = str(side)

            # Create new row with explicit types
            new_row = pl.DataFrame([{
                "timestamp": timestamp,
                "symbol": symbol,
                "side": side,
                "price": price,
                "cycleBuy": cycleBuy
            }], schema=self.schema)

            # Add to the appropriate file (run in thread pool)
            if type == "raw":
                self.rawFile = await asyncio.to_thread(
                    lambda: pl.concat([self.rawFile, new_row])
                )
            else:
                self.dsrFile = await asyncio.to_thread(
                    lambda: pl.concat([self.dsrFile, new_row])
                )

        except Exception as e:
            print(f"Error adding new signal: {e}")