import os
import json
import time
import pandas as pd
import asyncio
from datetime import datetime, timedelta

class truthCompass:
    def __init__(self, ttl=30*86400):
        """Initialize truthCompass with data directory and TTL in seconds."""
        # Make sure logs directory exists
        os.makedirs("logs", exist_ok=True)
        self.default_ttl = ttl


#    def create_init_trading_df(self, symbols_list):
#        symbol_data_list = []
#        for symbol in symbols_list:
#            symbol_data_list.append({
#                'symbol': symbol,
#                'dollar_value': 0.0,
#                'buy_price': 0,
#                'dca_buys': 0,
#                'trade_cycles': 0,
#                'id': 0
#            })
#        # Create DataFrame directly from the list
#        df = pd.DataFrame(symbol_data_list)
#        float_columns = ['buy_price', 'dollar_value' ]
#        for col in float_columns:
#            df[col] = df[col].astype(float)
#        float_columns = ['dca_buys', 'trade_cycles', 'id']
#        for col in float_columns:
#            df[col] = df[col].astype(int)
#        return df.set_index('symbol')

    def refresh_certain_row(self, df, symbol, **kwargs):
        # Direct access by index is much faster
        for column, value in kwargs.items():
            if column in df.columns:
                df.at[symbol, column] = value
        return df
    
    def symbol_or_value_exists(self, df, column, value):
        if column == 'symbol' and df.index.name == 'symbol':
            # Check the index instead
            return value in df.index
        elif column in df.columns:
            # Check the column
            return value in df[column].values
        else:
            return False
    
    def add_new_row(self, df, symbol, dollar_value, buy_price, dca_buys, trade_cycles, id, timestamp=None):
        # Use current time if no timestamp provided
        if timestamp is None:
            timestamp = time.time()
        else:
            timestamp = float(timestamp)

        # Create a new row without the index columns
        new_row = {
            'dollar_value': float(dollar_value),
            'buy_price': float(buy_price),
            'dca_buys': int(dca_buys),
            'trade_cycles': int(trade_cycles),
            'id': int(id)
        }

        # Create a DataFrame with the MultiIndex
        new_row_df = pd.DataFrame([new_row], index=pd.MultiIndex.from_tuples([(symbol, timestamp)], names=['symbol', 'timestamp']))

        # Concatenate with the existing DataFrame
        return pd.concat([df, new_row_df])
    
    def load_df(self, filename="trading_data.csv"):
        try:
            # Try to load existing file
            filepath = os.path.join("logs", filename)
            df = pd.read_csv(filepath, dtype={'dca_buys': int, 'trade_cycles': int, 'id': int})

            # No need to convert timestamp if keeping as float

            # Set both symbol and timestamp as a MultiIndex
            return df.set_index(['symbol', 'timestamp'])

        except:
            # File doesn't exist, create empty DataFrame with correct columns
            df = pd.DataFrame(columns=['dollar_value', 'buy_price', 'dca_buys', 
                                     'trade_cycles', 'id'])

            # Create an empty MultiIndex
            df.index = pd.MultiIndex.from_tuples([], names=['symbol', 'timestamp'])

            # Set correct types
            df['dollar_value'] = df['dollar_value'].astype(float)
            df['buy_price'] = df['buy_price'].astype(float)
            df['dca_buys'] = df['dca_buys'].astype(int)
            df['trade_cycles'] = df['trade_cycles'].astype(int)
            df['id'] = df['id'].astype(int)

            return df
        
    def save_df_to_file(self, df, filename="trading_data.csv"):
        try:
            filepath = os.path.join("logs", filename)
            df.to_csv(filepath, index=True)  # Changed to index=True
            return 1
        except Exception as e:
            print(f"Error saving file: {e}")  # Added error message
            return 0
        
    def get_latest_for_symbol(self, df, symbol):
        """Get the latest entry for a symbol using MultiIndex"""
        try:
            # This assumes df has a MultiIndex with (symbol, timestamp)
            if symbol not in df.index.get_level_values('symbol'):
                return None
                
            # Get all rows for this symbol and sort by timestamp (descending)
            symbol_data = df.xs(symbol, level='symbol').sort_index(ascending=False)
            
            # Return the first row (latest timestamp)
            return symbol_data.iloc[0]
        except Exception as e:
            print(f"Error: {e}")
            return None

    def check_if_duplicate(self,df, symbol, cycleBuy):
        try:
            latest_entry = self.get_latest_for_symbol(df, symbol)
            print(latest_entry)
            if latest_entry is None:
                # No entries for this symbol yet, so not a duplicate
                return False 
            print(latest_entry['dca_buys']) 

            if latest_entry['dca_buys'] == cycleBuy:
                # This would be a duplicate
                return True
            else:
                return True
        except Exception as e:
            print(f"Error: {e}")
            return None

#bot = truthCompass()
#df = bot.load_df()
#print(df)
#print("____________________________________________________________________")
#df_plus = bot.add_new_row(df, "HYPE/USDC:USDC", 12.1, 9000.0, 0, 0, 00000000000)
#print(df_plus)
#print("____________________________________________________________________")
#print(bot.save_df_to_file(df_plus))
#row = bot.get_latest_for_symbol(df_plus, "HYPE/USDC:USDC")
#print(row['dollar_value'])
#print(row)
#checker = bot.check_if_duplicate(df_plus, "HYPE/USDC:USDC", 0)
#print(checker)