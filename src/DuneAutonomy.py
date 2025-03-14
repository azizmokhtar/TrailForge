from hyperliquid import hyperLiquid
import pandas as pd
import asyncio
import ccxt
import time
import os
import datetime

# Setup logging to file
def log_to_file(message, level="INFO"):
    if level in ["ERROR", "TRADE", "WARNING", "INFO"]:  # Set which levels to log
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        
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
        log_to_file("HyperLiquid bot initialized")
        

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
            log_to_file(f"Error fetching Hyperliquid account info: {e}")
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
            log_to_file(f"Error fetching ticker for {symbol}: {e}")
            return None
        
    def setLeverage(self, leverage, symbol):
        try:
            self.exchange.set_leverage(leverage=leverage, symbol=symbol)
            log_to_file(f"Leverage set to {leverage}x for {symbol}")
        except Exception as e:
            log_to_file(f"Error setting leverage for {symbol}: {e}")

    def leveragedMarketOrder(self, symbol, side, amount):
        try:
            # Fetch the current price for the symbol
            ticker_data = self.fetchTicker(symbol) #  
            if not ticker_data:
                log_to_file(f"Failed to fetch ticker data for placing a market order on {symbol}")
                return None, None

            price = ticker_data["ask"] if side.lower() == "buy" else ticker_data["bid"]
            # Calculate the amount (in base asset) to achieve the desired order value
            amount_in_base = amount / price
            # Place the market order
            order = self.exchange.create_market_order(
                symbol=symbol,
                side=side.lower(),
                amount=amount_in_base,
                price=price,
            )
            # Extract relevant information from the order response
            buy_price = order['info']['filled']['avgPx']
            order_id = order['info']['filled']['oid']
            
            log_to_file(f"Market {side} order executed for {symbol}: ${amount} at price {buy_price}, order ID: {order_id}")

            return float(buy_price), order_id
        except Exception as e:
            log_to_file(f"Error placing leveraged market {side} order for {symbol}: {e}")
            return None, None
        
    def create_batch_limit_buy_order_custom_dca(self, pivot_price, base_amount, multiplier, symbol, deviations):
        orders = {}
        first_buy_base_amount = base_amount
        log_to_file(f"Creating batch limit buy orders for {symbol} with pivot price {pivot_price}")
        
        for deviation in deviations:
            price = pivot_price * (1 - deviation/100)
            log_to_file(f"Setting limit order for {symbol} at price {price} ({deviation}% below pivot)")
            
            base_amount = first_buy_base_amount*multiplier
            amount_in_base = base_amount / price
            
            try:
                order = self.exchange.create_limit_buy_order(
                    symbol,
                    amount_in_base,
                    price,
                    params={'postOnly': True}
                )
                
                orders[deviation] = order['info']['resting']['oid']
                log_to_file(f"Limit order placed for {symbol} at {price}: order ID {orders[deviation]}")
            except Exception as e:
                log_to_file(f"Error placing limit buy order for {symbol} at {price}: {e}")

        return orders
           
    def create_limit_sell_order(self, amount, symbol, deviation):
        try:
            ticker_data = self.fetchTicker(symbol) 
            if not ticker_data:
                log_to_file(f"Failed to fetch ticker data for placing a limit sell order on {symbol}")
                return None
                
            price = ticker_data["bid"] / (deviation+1)
            amount_in_base = amount / price
            
            log_to_file(f"Placing limit sell order for {symbol}: {amount_in_base} units at price {price}")
            
            order = self.exchange.create_limit_sell_order(
                symbol, 
                amount_in_base, 
                price, 
                #params ={'postOnly': True } THIS WILL MAKE IT FILL IF NOT LIMIT
            )
            order_id = order['info']['resting']['oid']
            log_to_file(f"Limit sell order placed for {symbol} at {price}: order ID {order_id}")
            return order_id
        except Exception as e:
            log_to_file(f"Error placing limit sell order for {symbol}: {e}")
            return None
        
    def cancelLimitOrders(self, deviations, symbol, order_ids):
        cancelled_count = 0
        failed_count = 0

        log_to_file(f"Cancelling limit orders for {symbol}")

        for deviation in deviations:
            if deviation in order_ids:
                order_id = order_ids[deviation]
                try:
                    # Attempt to cancel this specific order
                    cancelled_order = self.exchange.cancel_order(order_id, symbol)
                    log_to_file(f"Successfully canceled order for {symbol} at deviation {deviation}: order ID {order_id}")
                    cancelled_count += 1
                except Exception as e:
                    # If this specific order fails, log it but continue with others
                    log_to_file(f"Failed to cancel order for {symbol} at deviation {deviation}: order ID {order_id}, error: {e}")
                    failed_count += 1

        # Report summary
        log_to_file(f"Cancellation complete for {symbol}: {cancelled_count} orders canceled, {failed_count} failed")

        # Return failed_count if at least one order was canceled successfully
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
    # Create or clear log file at start
    with open("trading_bot_log.txt", "w") as log_file:
        log_file.write(f"=== HyperLiquid Trading Bot Started at {datetime.datetime.now()} ===\n")
    
    bot = hyperLiquid()
    utils = Utils()
    TP = 1
    deviation_pct = 2
    leverage = 3
    first_buy_lot = 11
    symbols = ["SUI/USDC:USDC", "AAVE/USDC:USDC", "HYPE/USDC:USDC", "ADA/USDC:USDC", "BTC/USDC:USDC"]
    SO_number = 5
    deviations = bot.create_limit_deviation_list(SO_number, deviation_pct)
    
    log_to_file(f"Bot configuration: TP={TP}%, Deviation={deviation_pct}%, Leverage={leverage}x, First buy=${first_buy_lot}")
    log_to_file(f"Trading symbols: {', '.join(symbols)}")
    log_to_file(f"DCA levels: {deviations}")
    
    # Fix: Assign the returned DataFrame back to trades_dashboard
    trades_dashboard = pd.DataFrame(columns=['symbol', 'size', 'pnl_pct', 'last_dca_price', 'dca_buys', 'trade_cycles', 'limit_orders'])
    trades_dashboard = utils.init_tradeables(trades_dashboard, symbols)
    
    log_to_file("Initial trades dashboard created")
    log_to_file(trades_dashboard.to_string())

    # Initial buy orders
    for index, row in trades_dashboard.iterrows():
        # check if current size is bigger than previous one
        if row['size'] == 0:
            symbol = row['symbol']
            bot.setLeverage(leverage, symbol)
            
            log_to_file(f"Buying ${first_buy_lot} of {symbol}")
            first_buy_order = bot.leveragedMarketOrder(symbol, 'buy', first_buy_lot)
            if first_buy_order[0] is not None:  # Check that order was placed successfully
                avg_price = first_buy_order[0]
                #log_to_file(f"Setting up DCA levels for {symbol} from base price {avg_price}")
                
                # Store limit orders in the dashboard
                limit_orders = bot.create_batch_limit_buy_order_custom_dca(avg_price, 11, 1, symbol, deviations)
                trades_dashboard.at[index, 'limit_orders'] = limit_orders
                trades_dashboard.at[index, 'dca_buys'] += 1
                trades_dashboard.at[index, 'last_dca_price'] = avg_price
                log_to_file(f"Initial buy complete for {symbol} at {avg_price}")
    
    # Main trading loop
    try:

        while True:
            #log_to_file(f"=== Trading cycle {cycle_count} started ===")
            
            # Get positions data - positions() returns (account_summary, positions_df)
            account_summary, positions_df = bot.positions()
            
            if positions_df is None:
                log_to_file("Failed to fetch positions, retrying in next cycle")
                time.sleep(60)
                continue
                
            # Log positions data to file
            if not positions_df.empty:
                log_to_file("Current positions:")
                log_to_file(positions_df.to_string())
            else:
                log_to_file("No active positions found")
            
            # Process each position that exists
            if not positions_df.empty:
                for index, row in positions_df.iterrows():
                    coin = row['symbol']  # This is just the coin name like "HYPE"
                    full_symbol = get_full_symbol(coin)  # Convert to "HYPE/USDC:USDC" format
                    
                    # Find the corresponding row in trades_dashboard
                    dashboard_idx = trades_dashboard.index[trades_dashboard['symbol'] == full_symbol].tolist()
                    
                    if dashboard_idx:
                        dashboard_idx = dashboard_idx[0]
                        
                        # Update dashboard with position data
                        trades_dashboard.at[dashboard_idx, 'size'] = row['position_value']
                        trades_dashboard.at[dashboard_idx, 'pnl_pct'] = row['pnl_pct']
                        trades_dashboard.at[dashboard_idx, 'last_dca_price'] = row['entry_price']
                        
                        #log_to_file(f"Updated {full_symbol} position: Value=${row['position_value']}, P&L={row['pnl_pct']:.2f}%, Entry=${row['entry_price']}")
                        
                        # Check for take profit
                        if row['pnl_pct'] > TP:
                            log_to_file(f"TAKE PROFIT: {full_symbol} is up {row['pnl_pct']:.2f}% (above {TP}% target) - closing position")
                            limit_orders = trades_dashboard.at[dashboard_idx, 'limit_orders']
                            bot.create_limit_sell_order(abs(row['size']), full_symbol, deviation=0)
                            filled_limit_orders = bot.cancelLimitOrders(deviations, full_symbol, limit_orders)
                            trades_dashboard.at[dashboard_idx, 'dca_buys'] += filled_limit_orders
                            trades_dashboard.at[dashboard_idx, 'last_dca_price'] = 0
                            trades_dashboard.at[dashboard_idx, 'trade_cycles'] += 1
                            trades_dashboard.at[dashboard_idx, 'size'] = 0
                            trades_dashboard.at[dashboard_idx, 'limit_orders'] = {}
                            #log_to_file(f"Position closed for {full_symbol}, trade cycle completed")
                        
                        elif row['size'] < 0:
                            log_to_file(f"WARNING: Short position detected for {full_symbol}. This strategy is for long positions only.")
            
            # Check for symbols that need new positions
            # First, get a list of all coins we have positions for
            active_coins = positions_df['symbol'].tolist() if not positions_df.empty else []
            
            # Check each trading symbol if it needs a new position
            for symbol in symbols:
                coin = get_coin_from_symbol(symbol)  # Extract "SUI" from "SUI/USDC:USDC"
                dashboard_idx = trades_dashboard.index[trades_dashboard['symbol'] == symbol].tolist()
                
                if not dashboard_idx:
                    continue
                
                dashboard_idx = dashboard_idx[0]
                
                # If this coin is not in our active positions and dashboard shows size=0, start a new position
                if coin not in active_coins and trades_dashboard.at[dashboard_idx, 'size'] == 0:
                    log_to_file(f"No position for {symbol}, initiating new buy with ${first_buy_lot}")
                    bot.setLeverage(leverage, symbol)
                    first_buy_order = bot.leveragedMarketOrder(symbol, 'buy', first_buy_lot)
                    
                    if first_buy_order[0] is not None:
                        avg_price = first_buy_order[0]
                        #log_to_file(f"Setting up DCA levels for {symbol}")
                        limit_orders = bot.create_batch_limit_buy_order_custom_dca(avg_price, first_buy_lot, 1, symbol, deviations)
                        
                        trades_dashboard.at[dashboard_idx, 'limit_orders'] = limit_orders
                        trades_dashboard.at[dashboard_idx, 'dca_buys'] += 1
                        trades_dashboard.at[dashboard_idx, 'last_dca_price'] = avg_price
                        trades_dashboard.at[dashboard_idx, 'size'] = first_buy_lot / avg_price  # Approximate size
                        #log_to_file(f"Initial buy complete for {symbol} at {avg_price}")

            # Log the current dashboard state
            #log_to_file("Current trades dashboard:")
            #log_to_file(trades_dashboard[['symbol', 'size', 'pnl_pct', 'dca_buys', 'trade_cycles']].to_string())
            
            # Log account summary if available
            #if account_summary:
                #log_to_file(f"Account summary: Value=${account_summary['account_value']:.2f}, Free=${account_summary['free_balance']:.2f}, Used margin=${account_summary['used_margin']:.2f}")

            # Sleep before next cycle
            #log_to_file(f"Sleeping for 60 seconds before next cycle")
            time.sleep(60)
    
    except KeyboardInterrupt:
        log_to_file("Bot stopped by user")
    except Exception as e:
        log_to_file(f"ERROR in main loop: {e}")
        log_to_file(f"Error details: {str(e)}")
        raise

if __name__ == "__main__":
    main()