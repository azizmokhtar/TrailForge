import os
import json
import time
import polars as pl
from datetime import datetime, timedelta

class truthCompass:
    def __init__(self, symbol, ttl=30*86400):
        """Initialize truthCompass with data directory and TTL in seconds."""
        # Make sure logs directory exists
        os.makedirs("logs", exist_ok=True)
        self.symbol = symbol
        self.default_ttl = ttl
        
        # Get file paths
        self.dsrFilePath, self.rawFilePath = self.getFilepath(symbol)
        
        # Define schema with explicit types to prevent type mismatches
        self.schema = {
            "timestamp": pl.Datetime,
            "symbol": pl.Utf8,
            "side": pl.Utf8,
            "price": pl.Float64,
            "cycleBuy": pl.Int64,
        }
        
        # Load existing data or create empty DataFrame with explicit schema
        if os.path.exists(self.rawFilePath):
            self.rawFile = pl.read_parquet(self.rawFilePath)
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
            
        if os.path.exists(self.dsrFilePath):
            self.dsrFile = pl.read_parquet(self.dsrFilePath)
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
    
    def getFilepath(self, symbol):
        """Generate filepath for storing order history."""
        dsrFile = f"logs/dsr_{symbol.lower()}_signal.parquet"
        rawFile = f"logs/raw_{symbol.lower()}_signal.parquet"
        return dsrFile, rawFile
    
    def save(self):
        """Save dataframes to disk."""
        self.rawFile.write_parquet(self.rawFilePath)
        self.dsrFile.write_parquet(self.dsrFilePath)
    
    def checkAndUpdate(self, symbol, side, price, cycleBuy):
        """
        Update the signal in the timed list and return status.
        
        Args:
            symbol (str): Trading symbol
            side (str): 'buy' or 'sell'
            price (float): Trade price
            cycleBuy (int or str): Cycle buy number
            
        Returns:
            int: 0 if signal is new, 1 if it already exists
        """
        current_time = time.time()
        
        # Convert inputs to appropriate types for comparison
        price = float(price)
        cycleBuy = int(cycleBuy)
        side = str(side)
        
        
        # Remove expired signals (older than TTL)
        if not self.rawFile.is_empty():
            # Convert timestamp strings to epoch time for comparison
            expiration_datetime = datetime.now() - timedelta(seconds=self.default_ttl)

            # Then filter using datetime comparison
            self.rawFile = self.rawFile.filter(
                pl.col("timestamp") > expiration_datetime
            )
                    
        # Check if signal exists in DSR file
        if not self.dsrFile.is_empty():
            matches = self.dsrFile.filter(
                (pl.col("symbol") == symbol) & 
                (pl.col("price") == price) & 
                (pl.col("side") == side) & 
                (pl.col("cycleBuy") == cycleBuy)
            )
            
            if matches.height > 0:
                # Signal already exists in DSR
                return 1
            
        self.addNewSignal("dsr", symbol, side, price, cycleBuy)

        # Save changes
        self.save()
        return 0
    
    def addNewSignal(self, type, symbol, side, price, cycleBuy):
        """
        Add a new signal to either the raw or DSR file.

        Args:
            type (str): "raw" or "dsr" to specify which file to add to
            symbol (str): Trading symbol
            side (str): 'buy' or 'sell'
            price (float): Trade price
            cycleBuy (int): Cycle buy number
        """
        try:
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

            # Add to the appropriate file
            if type == "raw":
                self.rawFile = pl.concat([self.rawFile, new_row])
            else:
                self.dsrFile = pl.concat([self.dsrFile, new_row])

            # Note: We don't save here to avoid duplicate saves
            # Saving should happen in the calling method

        except Exception as e:
            print(f"Error adding new signal: {e}")
            # Consider more robust error handling here

