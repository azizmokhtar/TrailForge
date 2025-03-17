import logging
from hyperliquid import hyperLiquid
from utils import utils
import asyncio
import time

async def main():
    ################## VARIABLES ######################## 
    TP = 1  # works as ttp activation also
    TSL = 0.005
    deviations = [1, 1.6, 6, 13, 29]
    multiplier = 2  # to put the average between last so lines
    symbols = ["HYPE/USDC:USDC", "ADA/USDC:USDC"]
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
    
    #for symbol in trade_df.index:
    #        print(symbol)
    #        base_currency = symbol.replace("/USDC:USDC", "") # eformat just to fetch openpositions func
    #        account_data, positions_df = await bot.positions()
    #        free_balance = account_data['free_balance']
    #        print(f"free balance is: {free_balance}")
    #        print(f"positions df: {positions_df}")
   #
    #        # Only try to access the symbol column if it exists
    #        if not positions_df.empty:
    #            print("positions not empty")
    #            print(utils_instance.symbol_or_value_exists(positions_df, 'symbol', base_currency))
    #            if utils_instance.symbol_or_value_exists(positions_df, 'symbol', base_currency):
    #                
    #                position_open = True
    #                print("Symbol column values:", positions_df['symbol'].tolist())
    #            else:
    #                print(f"{symbol} not open")
#
    #        else:
    #            print("positions df empty")
    while True:
        for symbol in trade_df.index:
            print(symbol)
            position_open = False
            position_data = None
            base_currency = symbol.replace("/USDC:USDC", "") # eformat just to fetch openpositions func
            account_data, positions_df = await bot.positions()
            free_balance = account_data['free_balance']
            print(f"free_balance is : {free_balance}")
            order_size = free_balance * first_buy_pct  # Use first_buy_pct instead of hardcoded 0.1
            if order_size < 11:
                order_size = 11

                        # Replace the position detection and handling code with this
            print(f"positions df is: {positions_df}")

            

            # Check if we have a position for this symbol
            if not positions_df.empty:
                ticker_data = await bot.fetchTicker(symbol)
                current_price = float(ticker_data["last"])
                # Find any rows where the symbol column matches our symbol
                if utils_instance.symbol_or_value_exists(positions_df, 'symbol', base_currency):
                    position_data = positions_df[positions_df['symbol'] == base_currency].iloc[0].to_dict()
                    print(f"pnl pct is: {position_data['pnl_pct']}")
                    position_pnl_pct = position_data['pnl_pct']
                    position_value = position_data['position_value']
                    # Just update our trade tracking df with current position info
                    trade_df = utils_instance.refresh_certain_row(
                        trade_df,
                        symbol,
                        open=True,
                        pnl_pct=position_pnl_pct,
                        size=position_value,
                    )
                    print(f"Updated position info for {symbol}")

                    if position_pnl_pct > TP:
                        tsl_triggered[symbol] = True
                        if current_price > high_prices[symbol]:
                            high_prices[symbol] = current_price

                    if tsl_triggered[symbol] and ((high_prices[symbol] - current_price) / high_prices[symbol]) > TSL:
                        print(f"TSL triggered for {symbol}, closing position")
                        close_order = await bot.leveraged_market_close_Order(symbol, "buy")
                        if close_order[0] is None:
                            print({"status": "error", "message": "Failed to execute sell order"})
                        print(f"cancelling limit orders")
                        filled_orders = await bot.cancelLimitOrders(deviations, symbol, trade_df.at[symbol, 'limit_orders'])
                        print("refreshing df")
                        trade_df = utils_instance.refresh_certain_row(
                            trade_df,
                            symbol,
                            open=False,
                            pnl_pct=0.0,
                            size=0.0,
                            dca_buys=0,
                            last_dca_price=0.0,
                            limit_orders={}
                        )
                else:
                    print(f"NO position, opening one for {symbol}")
                            # Need to await this async function
                    try:
                        await bot.setLeverage(5, symbol)
                    except Exception as e:
                        print(f"Error setting leverage: {e}")
                        # Continue even if leverage setting fails - the API may have default leverage
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
                        pnl_pct= 0.0,
                        dca_buys=1,
                        last_dca_price=avg_price,
                        limit_orders=limit_orders
                    )


            elif not position_open:
                # No position exists, open a new one
                print(f"NO position, opening one for {symbol}")
                            # Need to await this async function
                try:
                    await bot.setLeverage(5, symbol)
                    print("Leverage set")
                except Exception as e:
                    print(f"Error setting leverage: {e}")
                    # Continue even if leverage setting fails - the API may have default leverage
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
                    pnl_pct= 0.0,
                    dca_buys=1,
                    last_dca_price=avg_price,
                    limit_orders=limit_orders
                )
                print(f"params set")

            await asyncio.sleep(5)  # Use asyncio.sleep instead of time.sleep in async functions
                
        print("nothing new")
        print(trade_df)
        print("nothing new, sleeping 60s !")
        await asyncio.sleep(20)

# Run the main function with asyncio
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"An error occurred: {e}")
        # Add more detailed error reporting
        import traceback
        traceback.print_exc()

