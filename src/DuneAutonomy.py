import logging
from hyperliquid import hyperLiquid
from utils import utils
import asyncio
import time

async def main():
    ################## VARIABLES ########################
    TP = 1  # works as ttp activation also
    TSL = 0.05
    deviations = [1, 1.6, 6, 13, 29]
    multiplier = 2.75  # to put the average between last so lines
    symbols = ["HYPE/USDC:USDC", "ADA/USDC:USDC", "XRP/USDC:USDC", "ATOM/USDC:USDC", "SUI/USDC:USDC"]
    first_buy_pct = 0.01  # percent of order size according to the fund
    
    ################## SETTING VALUES AND INSTANCES #####
    # Initialize bot with proper authentication
    wallet_address = input("Enter your wallet address: ")
    private_key = input("Enter your private key: ")
    bot = await hyperLiquid.create(wallet_address, private_key)
    
    utils_instance = utils()
    trade_df = utils_instance.create_init_trading_df(symbols)
    
    high_prices = {symbol: 0.0 for symbol in symbols}
    tsl_triggered = {symbol: False for symbol in symbols}
    
    
    while True:
        for symbol in trade_df.index:

            account_data, positions_df = await bot.positions()
            free_balance = account_data['free_balance']
            order_size = free_balance * first_buy_pct  # Use first_buy_pct instead of hardcoded 0.1
            if order_size < 11:
                order_size = 11
                
            print(positions_df)
            if utils_instance.symbol_or_value_exists(positions_df, 'symbol', symbol):
                print(f"{symbol} position found")
                position_entry_price = positions_df.at[symbol, 'entry_price']
                position_pnl_pct = positions_df.at[symbol, 'pnl_pct']
                # Fix variable name (trades_dashboard to positions_df) and access method
                ticker_data = await bot.fetchTicker()
                current_price = float(ticker_data["last"])
                if symbol in positions_df.index and positions_df.at[symbol, 'pnl_pct'] > TP:
                    tsl_triggered[symbol] = True
                    if current_price > high_prices[symbol]:
                        high_prices[symbol] = current_price
                    
                if tsl_triggered[symbol] == True and ((high_prices[symbol]- current_price)/ high_prices[symbol]) > TSL:
                    close_order = await bot.leveraged_market_close_Order(symbol, "buy")
                    if close_order[0] is None:
                        print({"status": "error", "message": "Failed to execute sell order"})
                        continue
                    
                    print(f"cancelling limit orders")
                    # Fix variable name from trades_df to trade_df
                    filled_orders = await bot.cancelLimitOrders(deviations, symbol, trade_df.at[symbol, 'limit_orders'])

                    print("refreshing df")
                    trade_df = utils_instance.refresh_certain_row(
                        trade_df,
                        symbol,
                        open=False,
                        size=0.0,
                        dca_buys=0,  # Integer instead of float
                        last_dca_price=0.0,
                        limit_orders={}  # Empty dict instead of 0.0
                    )
            elif trade_df.at[symbol, 'open'] == False:
                print(f"NO position, opening one for {symbol}")
                # Need to await this async function
                await bot.setLeverage(5, symbol)
                first_buy_order = await bot.leveragedMarketOrder(symbol, "buy", order_size)

                if first_buy_order[0] is None:
                    print({"status": "error", "message": "Failed to execute buy order"})
                    continue

                print(f"order created")
                avg_price = first_buy_order[0]
                limit_orders = await bot.create_batch_limit_buy_order_custom_dca(
                    avg_price, order_size, multiplier, symbol, deviations
                )

                # Fix variable name from trades_df to trade_df
                trade_df = utils_instance.refresh_certain_row(
                    trade_df,
                    symbol,
                    open=True,
                    dollar_value=order_size,
                    size=order_size,
                    dca_buys=1,
                    last_dca_price=avg_price,
                    limit_orders=limit_orders
                )

                print(f"params set")
            
            else:
            # Sleep between iterations
                print(f"checked {symbol}, pnl: {positions_df.at[symbol, 'pnl_pct']}")
                await asyncio.sleep(5)  # Use asyncio.sleep instead of time.sleep in async functions
        print("nothing new")
        print(trade_df)
        print("nothing new, sleeping 60s !")
        await asyncio.sleep(60)

# Run the main function with asyncio
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"An error occurred: {e}")













