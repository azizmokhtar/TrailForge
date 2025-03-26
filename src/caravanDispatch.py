######################################
#CHANGES TO IMPLEMENT:
# solidify truthCompass
# Work on shorting
# look for feedback
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel
import logging
import asyncio
from src.hyperliquid import hyperLiquid
from config.hyperliquid_symbol_map import hyperliquid_symbol_mapper
from src.truthCompass import truthCompass
from src.telegramMessenger import Messenger

# Global bot instance that will be initialized at startup
bot = None
filter = None
telegram = None

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the bot
    global bot, telegram
    print("Initializing trading bot...")
    # Create the bot instance and prompt for credentials
    bot = await hyperLiquid.create()
    telegram = Messenger()
    print("Bot successfully initialized and ready to receive trading signals.")
    
    yield  # This is where FastAPI serves requests
    
    # Shutdown: Cleanup (if needed)
    print("Shutting down trading bot...")
    # Add any cleanup code here if needed

# Initialize FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)
class WebhookPayload(BaseModel):
    event: str
    data: dict

@app.post("/")
async def webhook(request: Request):
    global bot, telegram
    
    # Check if bot is initialized
    if bot is None:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    if telegram is None:
        print("Telegram session could not be established!")
        
    try:
        # Parse the incoming JSON payload
        payload = await request.json()
        print("Received webhook data:", payload)
        
        # Validate the payload against the WebhookPayload model
        webhook_payload = WebhookPayload(**payload)
        event = webhook_payload.event
        data = webhook_payload.data
        
        # Extract required fields from the payload
        symbol = data.get("symbol")
        ticker = hyperliquid_symbol_mapper.get(symbol)
        amount = int(data.get("amount"))  # can be dynamic, as long as > 11$
        leverage = int(data.get("leverage"))
        price = float(data.get("price"))
        cycleBuy = int(data.get("cycleBuys"))

        if not ticker or not leverage or not amount:
            return {"status": "error", "message": f"Invalid or lacking payload"}


        availe_open_size = await bot.get_position_size(symbol)
        availe_open_size = availe_open_size[0]
        dsr = truthCompass()
        trades = dsr.load_df()
        checker = dsr.check_if_duplicate(trades, ticker, cycleBuy, availe_open_size) 
        
        print(f"checking event {event}, ticker: {ticker}, cycleBuys: {cycleBuy}")
        # Case of market buy
        print(f"checker : {checker}")
        if event == "buy" and checker == False:
            print("event buy, buying now")
            leverage = await bot.setLeverage(leverage, ticker)
            order = await bot.leveragedMarketOrder(ticker, "Buy", amount)
            if order[0] == None:
                return {"status": "error", "message": "Failed to execute buy order"}
            # Log the order details
            trades = dsr.add_new_row(trades, ticker, amount, order[0], cycleBuy, 0, order[1])
            dsr.save_df_to_file(trades)
            # Send to telegram 
            if cycleBuy==1:
                await telegram.send_message(text=f'- {symbol.upper()} Cycle Buy initiated, at price {order[0]}$')
            else:
                await telegram.send_message(text=f'- {symbol.upper()} DCA number {cycleBuy} executed, at price {order[0]}$')
            return {
                "status": "buy order success", 
                "message": "Buy order executed", 
                "result": [{order[0]}, {order[1]}]
            }
            
        # Case of market close order/ TODO: case of shorting
        elif event == "sell" and checker == False:
            print("event sell, selling now")
            order = await bot.leveraged_market_close_Order(ticker, "buy")
            if order[0] == None :
                return {"status": "error", "message": "Failed to execute sell order"}
            # Log the order details
            trades = dsr.add_new_row(trades, ticker, amount, order[0], cycleBuy, 0, order[1])
            dsr.save_df_to_file(trades)
            # Send to telegram
            await telegram.send_message(text=f'- {symbol.upper()} cycle complete, exit price {order[0]}$')
            return {
                "status": "sell order success", 
                "message": "Sell order executed", 
                "result": [{order[0]}, {order[1]}]
            }
            
        else:
            return {"status": "error", "message": f"Unknown event: {event}"}
            
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)  # Run on port 80