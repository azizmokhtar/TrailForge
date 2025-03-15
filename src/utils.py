import pandas as pd

class utils:

    def create_init_trading_df(self, symbols_list):
        symbol_data_list = []
        for symbol in symbols_list:
            symbol_data_list.append({
                'symbol': symbol,
                'open': False,  # This will stay as boolean
                'size': 0.0,
                'dollar_value': 0.0,
                'pnl_pct': 0.0,
                'last_dca_price': 0,
                'dca_buys': 0,
                'trade_cycles': 0,
                'limit_orders': {}
            })
        # Create DataFrame directly from the list
        df = pd.DataFrame(symbol_data_list)
        return df.set_index('symbol')

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
    



utilitiy = utils()
symbols = [ "ADA/USDC:USDC","BTC/USDC:USDC","SOL/USDC:USDC","XRP/USDC:USDC"]
pdff = utilitiy.create_init_trading_df(symbols)
print(pdff)
buys = 3
refreshed_df = utilitiy.refresh_certain_row(pdff,"ADA/USDC:USDC", dca_buys = buys, size=2 )
print(refreshed_df)
symbol_exists = utilitiy.symbol_or_value_exists(refreshed_df, 'symbol', "ADA/USDC:USDC")
print(symbol_exists)
three_exists = utilitiy.symbol_or_value_exists(refreshed_df, 'dca_buys', 3)
print(three_exists)