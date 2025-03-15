from hyperliquid import hyperLiquid
import pandas as pd
import asyncio
import ccxt
import time
import os
import datetime

# Setup logging to file
def log_to_file(message):
    """Write log message to a file with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    
    with open("trading_bot_log.txt", "a") as log_file:
        log_file.write(log_entry)

class Utils:
    #========================================================================================
    # for a df of this format: columns=['symbol', 'size', 'last_dca_price', 'dca_buys', 'trade_cycles'])
    #========================================================================================

    @staticmethod
    def init_tradeables(df, symbols_list):
        symbol_data_list = []
        for symbol in symbols_list:
            symbol_data_list.append({
                'symbol': symbol,
                'size': 0.0,
                'pnl_pct': 0.0,
                'last_dca_price': 0,
                'dca_buys': 0,
                'trade_cycles': 0,
                'limit_orders': {}  # Store limit orders by deviation
            })
        
        # Add all rows to the DataFrame at once
        return pd.concat([df, pd.DataFrame(symbol_data_list)], ignore_index=True)

class hyperLiquid:
    def __init__(self):
        self.exchange = ccxt.hyperliquid({
            "walletAddress": "0x673Aa1aF74F2436BCbA24DC2A80089B77A3D10e8",
            "privateKey": "0xe4ac2035a8ac1052cc93e92592398bd4644ef7cec1352126543c0fa6a806e4aa",
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
                "network": "mainnet",
            },
        })
        

    def positions(self):
        try:
            # Fetch the balance information
            balance_info = self.exchange.fetch_balance()

            # Extract account value and liquidity information
            account_value = float(balance_info['info']['marginSummary']['accountValue'])
            free_balance = float(balance_info['info']['marginSummary']['totalRawUsd'])
            used_margin = float(balance_info['info']['marginSummary']['totalMarginUsed'])
            withdrawable = float(balance_info['info']['withdrawable'])

            # Extract risk management information
            maintenance_margin = float(balance_info['info']['crossMaintenanceMarginUsed'])

            # Initialize variables for position information
            positions_list = []  # Renamed to avoid conflict

            # Extract position details from assetPositions
            for asset_position in balance_info['info']['assetPositions']:
                if 'position' in asset_position:
                    position = asset_position['position']

                    coin = position['coin']
                    size = float(position['szi'])
                    entry_price = float(position['entryPx'])
                    position_value = float(position['positionValue'])
                    side = "long" if position_value >= 0 else "short"
                    unrealized_pnl = float(position['unrealizedPnl'])
                    return_on_equity = float(position['returnOnEquity'])

                    # Check if liquidationPx exists and is not None
                    liquidation_price = None
                    if 'liquidationPx' in position and position['liquidationPx'] is not None:
                        liquidation_price = float(position['liquidationPx'])

                    margin_used = float(position['marginUsed'])
                    max_leverage = float(position['maxLeverage'])

                    # Extract funding information with error handling
                    funding_data = {}
                    if 'cumFunding' in position:
                        funding = position['cumFunding']
                        funding_data = {
                            'all_time': float(funding.get('allTime', 0)),
                            'since_open': float(funding.get('sinceOpen', 0)),
                            'since_change': float(funding.get('sinceChange', 0))
                        }
                    else:
                        funding_data = {
                            'all_time': 0.0,
                            'since_open': 0.0,
                            'since_change': 0.0
                        }

                    # Get leverage value
                    if 'leverage' in position and 'value' in position['leverage']:
                        leverage = float(position['leverage']['value'])
                        leverage_type = position['leverage']['type']
                    else:
                        leverage = 1.0
                        leverage_type = "unknown"

                    # Create position object
                    position_info = {
                        'symbol': coin,
                        'size': size,
                        'side': side,
                        'entry_price': entry_price,
                        'position_value': position_value,
                        'unrealized_pnl': unrealized_pnl,
                        'pnl_pct': return_on_equity,
                        'liquidation_price': liquidation_price,
                        'margin_used': margin_used,
                        'max_leverage': max_leverage,
                        'leverage': leverage,
                        'leverage_type': leverage_type,
                        'funding': funding_data
                    }

                    positions_list.append(position_info)

            # Create a summary object with all extracted information
            account_summary = {
                'account_value': account_value,
                'free_balance': free_balance,
                'used_margin': used_margin,
                'withdrawable': withdrawable,
                'maintenance_margin': maintenance_margin,
                'positions': positions_list,
                'timestamp': balance_info['timestamp']
            }

            # Create DataFrame if positions exist
            if positions_list:
                positions_df = pd.DataFrame(positions_list)
                positions_df['pnl_pct'] = positions_df['pnl_pct'] * 100
                # Create a copy of funding data before dropping
                if 'funding' in positions_df.columns:
                    positions_df['funding_since_open'] = positions_df['funding'].apply(lambda x: x.get('since_open', 0))

                # Drop columns
                columns_to_drop = []
                for col in ['liquidation_price', 'max_leverage', 'leverage_type', 'funding']:
                    if col in positions_df.columns:
                        columns_to_drop.append(col)

                if columns_to_drop:
                    positions_df = positions_df.drop(columns=columns_to_drop)

                return account_summary, positions_df
            else:
                # Return empty DataFrame if no positions
                return account_summary, pd.DataFrame()

        except Exception as e:
            print(f"Error fetching Hyperliquid account info: {e}")
            return None, None  # Return None, None instead of just None
        
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
        
    def setLeverage(self, leverage, symbol):
        try:
            self.exchange.set_leverage(leverage=leverage, symbol=symbol)
            print("Leverage set")
        except Exception as e:
            print(f"Error setting leverage: {e}")

    def leveragedMarketOrder(self, symbol, side, amount):
        try:
            # Fetch the current price for the symbol
            ticker_data = self.fetchTicker(symbol) #  
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

            return float(buy_price), order_id
        except Exception as e:
            print(f"Error placing leveraged market {side} order: {e}")
            return None, None
        
    def create_batch_limit_buy_order_custom_dca(self, pivot_price, base_amount, multiplier, symbol, deviations):
        orders = {}
        first_buy_base_amount = base_amount
        for deviation in deviations:
            price = pivot_price * (1 - deviation/100)
            print(f"price is {price}")
            base_amount = first_buy_base_amount*multiplier
            amount_in_base = base_amount / price
            order = self.exchange.create_limit_buy_order(
            symbol,
            amount_in_base,
            price,
            params={'postOnly': True}
            )
        
            orders[deviation] = order['info']['resting']['oid']

        return orders
           
    def create_limit_sell_order(self, amount, symbol, deviation):
        try:
            ticker_data = self.exchange.fetchTicker(symbol) 
            if not ticker_data:
                print("Failed to fetch ticker data for placing a market order!")
                return None, None
            price = ticker_data["bid"] / (deviation+1)
            amount_in_base = amount / price
            order = self.exchange.create_limit_sell_order(
                symbol, 
                amount_in_base, 
                price, 
                #params ={'postOnly': True } THIS WILL MAKE IT FILL IF NOT LIMIT
            )
            order_id = order['info']['resting']['oid']
            return order_id
        except Exception as e:
            print(f"Error placing leveraged limit buy order: {e}")
            return None
        
    def cancelLimitOrders(self, deviations, symbol, order_ids):

        cancelled_count = 0
        failed_count = 0

        for deviation in deviations:
            if deviation in order_ids:
                order_id = order_ids[deviation]
                try:
                    # Attempt to cancel this specific order
                    cancelled_order = self.exchange.cancel_order(order_id, symbol)
                    print(f"Successfully canceled order for deviation {deviation}")
                    cancelled_count += 1
                except Exception as e:
                    # If this specific order fails, log it but continue with others
                    print(f"Failed to cancel order for deviation {deviation}, error: {e}")
                    failed_count += 1

        # Report summary
        print(f"Cancellation complete: {cancelled_count} orders canceled, {failed_count} failed")

        # Return 1 if at least one order was canceled successfully
        return failed_count if cancelled_count > 0 else 0

    def create_limit_deviation_list(self, number_of_levels, deviation):
        deviations = []
        for i in range(1, number_of_levels + 1):  # Start from 1 and go up to number_of_levels
            deviations.append(deviation * i)
        return deviations
    
# Get full trading symbol from coin
def get_full_symbol(coin):
    return f"{coin}/USDC:USDC"

# Extract coin name from full trading symbol
def get_coin_from_symbol(full_symbol):
    return full_symbol.split('/')[0]

# Main code
def main():
    bot = hyperLiquid()
    utils = Utils()
    TP = 1
    
    leverage = 2
    first_buy_lot = 11
    symbols = [ "ADA/USDC:USDC"]
    SO_number = 10
    deviation_pct = 1
    deviations= bot.create_limit_deviation_list(SO_number, deviation_pct)

    log_to_file(f"Bot configuration: TP={TP}%, Deviation={deviation_pct}%, Leverage={leverage}x, First buy=${first_buy_lot}")
    log_to_file(f"Trading symbols: {', '.join(symbols)}")
    log_to_file(f"DCA levels: {deviations}")
    # Fix: Assign the returned DataFrame back to trades_dashboard
    trades_dashboard = pd.DataFrame(columns=['symbol', 'size', 'pnl_pct', 'last_dca_price', 'dca_buys', 'trade_cycles', 'limit_orders'])
    trades_dashboard = Utils.init_tradeables(trades_dashboard, symbols)
    print("Initial trades dashboard:")
    print(trades_dashboard)


    try:
        while True:

            
            for index, row in trades_dashboard.iterrows():
            # check if current size is bigger than  previous one
                if row['size'] == 0:
                    symbol = row['symbol']
                    bot.setLeverage(leverage, symbol)

                    print(f"buying {first_buy_lot} $ of {symbol}")
                    first_buy_order = bot.leveragedMarketOrder(symbol, 'buy', first_buy_lot)
                    if first_buy_order[0] is not None:  # Check that order was placed successfully
                        avg_price = first_buy_order[0]
                        print(f"Deviations for DCA: {deviations}")
                        # Refresh dashboard
                        limit_orders = bot.create_batch_limit_buy_order_custom_dca(avg_price, 11, 1, symbol, deviations)
                        trades_dashboard.at[index, 'size'] = 1
                        #trades_dashboard.loc[trades_dashboard['symbol'] == symbol, 'pnl_pct'] += row['pnl_pct']
                        trades_dashboard.at[index, 'last_dca_price'] = avg_price
                        #trades_dashboard.loc[trades_dashboard['symbol'] == symbol, 'trade_cycles'] += 1
                        trades_dashboard.at[index, 'dca_buys'] += 1
                        trades_dashboard.at[index, 'limit_orders'] = limit_orders
                        log_to_file("Current trades dashboard:")
                        log_to_file(trades_dashboard[['symbol', 'size', 'pnl_pct', 'dca_buys', 'trade_cycles']].to_string())
                        log_to_file(f"Initial buy complete for {symbol} at {avg_price}")
                        print(f"Initial buy complete for {symbol} at {avg_price}")
                        
                        
            """Returns two instances:
                1: Complete overview of account: {'account_value': 697.548215, 'free_balance': 675.632015, 'used_margin': 21.5211, 'withdrawable': 676.027115, 'maintenance_margin': 0.93414, 'positions': [{'coin': 'BTC', 'size': 0.0004, 'entry_price': 82343.4, 'position_value': 32.4792, 'unrealized_pnl': -0.45816, 'return_on_equity': -0.0278200803, 'liquidation_price': None, 'margin_used': 16.2396, 'max_leverage': 40.0, 'leverage': 2.0, 'leverage_type': 'cross', 'funding': {'all_time': 0.249897, 'since_open': 0.003931, 'since_change': 0.002292}}, {'coin': 'ADA', 'size': -15.0, 'entry_price': 0.70452, 'position_value': 10.563, 'unrealized_pnl': 0.0048, 'return_on_equity': 0.0009084199, 'liquidation_price': 44.9336650794, 'margin_used': 5.2815, 'max_leverage': 10.0, 'leverage': 2.0, 'leverage_type': 'cross', 'funding': {'all_time': -0.074579, 'since_open': 0.0, 'since_change': 0.0}}], 'timestamp': 1741908024828}
                2: DF with openpositions:   symbol    size  side  entry_price  position_value  unrealized_pnl   pnl_pct  margin_used  leverage  funding_since_open
            """
            positions = bot.positions()[1]
            print(positions)
            for index, row in positions.iterrows():
                
                print(f"list is {index}")
                print(f"list is {row}")
# the exit order hits but it inverses it, meaning a bigger buy than the size, i would do a reduce only option and print the sizes for debugging,
#also check the symbol at if , what symbol is

                # Now use .at to access a single cell value
                if trades_dashboard.at[index, 'size'] == 0:
  
                    symbol = get_full_symbol(row['symbol'])
                    print(f"full symbol is {symbol}")
                    print(f"buying {first_buy_lot} $ of {symbol}")
                    first_buy_order = bot.leveragedMarketOrder(symbol, 'buy', first_buy_lot)
                    avg_price = first_buy_order[0]
                    print(f"deviations are {deviations}")
                    limit_orders = bot.create_batch_limit_buy_order_custom_dca(avg_price, 11, 1, symbol, deviations)
                    trades_dashboard.at[index, 'size'] = 1
                    #trades_dashboard.loc[trades_dashboard['symbol'] == symbol, 'pnl_pct'] += row['pnl_pct']
                    trades_dashboard.at[index, 'last_dca_price'] = avg_price
                    #trades_dashboard.loc[trades_dashboard['symbol'] == symbol, 'trade_cycles'] += 1
                    trades_dashboard.at[index, 'dca_buys'] += 1
                    trades_dashboard.at[index, 'limit_orders'] = limit_orders
                    log_to_file("Current trades dashboarDD:")
                    log_to_file(trades_dashboard[['symbol', 'size', 'pnl_pct', 'dca_buys', 'trade_cycles']].to_string())
                    print(limit_orders)
                    log_to_file(f"Initial buy complete for {symbol} at {avg_price}")

                    
                elif row['pnl_pct'] > TP:
                    print(f"{symbol} is up {TP} closing position now")
                    bot.create_limit_sell_order(abs(row['size']), symbol, deviation=0)
                    filled_limit_orders = bot.cancelLimitOrders(deviations, row['symbol'], limit_orders )
                    trades_dashboard.at[index, 'size'] = 0
                    trades_dashboard.loc[trades_dashboard['symbol'] == symbol, 'pnl_pct'] = 0
                    trades_dashboard.at[index, 'last_dca_price'] = 0
                    trades_dashboard.loc[trades_dashboard['symbol'] == symbol, 'trade_cycles'] += 1
                    trades_dashboard.at[index, 'dca_buys'] = 0
                    trades_dashboard.at[index, 'limit_orders'] = limit_orders 
                    log_to_file(f"Position closed for {symbol}, trade cycle completed")
                        
                        

                else:
                    trades_dashboard.at[index, 'size'] = 1
                    trades_dashboard.at[index, 'pnl_pct'] = row['pnl_pct']
                    #trades_dashboard.at[index, 'last_dca_price'] = 0
                    #trades_dashboard.loc[trades_dashboard['symbol'] == symbol, 'trade_cycles'] += 1
                    #trades_dashboard.at[index, 'dca_buys'] = 0
                    #trades_dashboard.at[index, 'limit_orders'] = limit_orders 
                    log_to_file(f"Updated {symbol} position: Value=${row['position_value']}, P&L={row['pnl_pct']:.2f}%, Entry=${row['entry_price']}")

            log_to_file("Current trades dashboard:")
            log_to_file(trades_dashboard[['symbol', 'size', 'pnl_pct', 'dca_buys', 'trade_cycles']].to_string())
            print("\nCurrent trades dashboard:")
            print(trades_dashboard[['symbol', 'size', 'pnl_pct', 'dca_buys', 'trade_cycles']])

            # Sleep before next cycle
            print(f"Sleeping for 60 seconds...")
            time.sleep(60)
    
    except KeyboardInterrupt:
        print("Bot stopped by user.")
    except Exception as e:
        print(f"Error in main loop: {e}")
        raise

if __name__ == "__main__":
    main()