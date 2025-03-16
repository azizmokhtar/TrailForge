from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel
import logging
from src.hyperliquid import hyperLiquid
from config.hyperliquid_symbol_map import hyperliquid_symbol_mapper
from src.truthCompass import truthCompass
from src.utils import utils

# Global bot instance that will be initialized at startup
bot = None
utility = None
trades_df = None
in_pos = False
first_entry_dollar_size = 11
SO_number = 10
deviation_pct = 1
deviations = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot, utility, trades_df, in_pos, SO_number, deviation_pct, deviations, deviation_pct
    utility = utils()
    symbols = ["ADA/USDC:USDC", "BTC/USDC:USDC", "SOL/USDC:USDC", "XRP/USDC:USDC", "ATOM/USDC:USDC", "SUI/USDC:USDC"]
    trades_df = utility.create_init_trading_df(symbols)
    bot = await hyperLiquid.create()# Create the bot instance and prompt for credentials
    deviations= bot.create_limit_deviation_list(SO_number, deviation_pct)
    yield  # This is where FastAPI serves requests
    print("Shutting down trading bot...")
    # Add any cleanup code here if needed

app = FastAPI(lifespan=lifespan)# Initialize FastAPI app with lifespan

class WebhookPayload(BaseModel):# Webhook format
    event: str
    data: dict

@app.post("/")
async def webhook(request: Request):
    global bot, utility, trades_df, in_pos, SO_number, deviation_pct, deviations, deviation_pct
    if bot is None:# Check if bot is initialized
        raise HTTPException(status_code=500, detail="Trading bot not initialized")  
    try:
        payload = await request.json()# Parse the incoming JSON payload
        print("Received webhook data:", payload)
        
        # Validate the payload against the WebhookPayload model
        webhook_payload = WebhookPayload(**payload)
        event = webhook_payload.event
        data = webhook_payload.data

        # Extract required fields from the payload
        symbol = data.get("symbol")
        amount = int(data.get("amount"))  # can be dynamic, as long as > 11$
        leverage = int(data.get("leverage"))
        price = float(data.get("price"))
        cycleBuy = int(data.get("cycleBuys"))

        if not symbol or not leverage or not amount or not cycleBuy:
            return {"status": "error", "message": f"Invalid or lacking payload"}
        
        ticker = hyperliquid_symbol_mapper.get(symbol)
        
        # Create truthCompass instance and check signal directly (no need for thread pool)
        tracker = truthCompass(symbol)
        await tracker.addNewSignal("raw", symbol, event, price, cycleBuy)
        await tracker.save()
        checker = await tracker.checkAndUpdate(symbol, event, price, cycleBuy)

        print(f"checking event {event}")
        # Case of market buy
        if event == "buy"  and trades_df.at[ticker, 'open'] == False:
            first_buy_order = await bot.leveragedMarketOrder(ticker, "buy", amount)
            if first_buy_order[0] == None:
                return {"status": "error", "message": "Failed to execute buy order"}
            print(f"order created")
            avg_price = first_buy_order[0]
            
            
            limit_orders = bot.create_batch_limit_buy_order_custom_dca(avg_price, first_entry_dollar_size, 1, ticker, deviations)
            trades_df = utility.refresh_certain_row(
                trades_df, 
                ticker, 
                open=True, 
                size=amount,
                dca_buys=cycleBuy,
                last_dca_price=price,
                limit_orders=limit_orders
            )
            print(f"params set")
            print(trades_df)
            
        elif event == "sell" and trades_df.at[ticker, 'open'] == True:
            close_order = await bot.leveraged_market_close_Order(ticker, "buy")
            if close_order[0] == None :
                return {"status": "error", "message": "Failed to execute sell order"}
            await bot.cancelLimitOrders(deviations, ticker, trades_df.at[symbol, 'limit_orders'])
            trades_df = utility.refresh_certain_row(
                trades_df, 
                ticker, 
                open=False, 
                size=0.0,
                dca_buys=0.0,
                last_dca_price=0.0,
                limit_orders=0.0,
            )
   

            
        else:
            return {"status": "error", "message": f"Unknown event: {event}"}
            
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)  # Run on port 80