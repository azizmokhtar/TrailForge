from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel
import logging
import aiofiles
from datetime import datetime
from src.hyperliquid import hyperLiquid
from config.hyperliquid_symbol_map import hyperliquid_symbol_mapper

# Global bot instance that will be initialized at startup
bot = None

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the bot
    global bot
    print("Initializing trading bot...")
    # Create the bot instance and prompt for credentials
    bot = await hyperLiquid.create()
    print("Bot successfully initialized and ready to receive trading signals.")
    
    yield  # This is where FastAPI serves requests
    
    # Shutdown: Cleanup (if needed)
    print("Shutting down trading bot...")
    # Add any cleanup code here if needed

# Initialize FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# Set up logging for orders
logging.basicConfig(
    filename='orders.log',
    level=logging.INFO,
    format='%(asctime)s - SIDE: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class WebhookPayload(BaseModel):
    event: str
    data: dict

# Async function to write to RawCompass file
async def writeUnfilteredSignals(exchange, asset, side, amount, price, cycleBuy):
    """Write received order details in logs directory to check when debugging TV"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    filename = f"logs/RawCompass.{exchange}.{asset}"
    try:
        async with aiofiles.open(filename, 'a') as file:
            await file.write(f"{timestamp} | {side} | Amount: {amount} | Price: {price} | cycleBuy: {cycleBuy}\n")
    except Exception as e:
        print(f"Error writing to RawCompass file: {e}")

@app.post("/")
async def webhook(request: Request):
    global bot
    
    # Check if bot is initialized
    if bot is None:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
        
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
        amount = data.get("amount")  # can be dynamic, as long as > 11$
        leverage = data.get("leverage")
        cycleBuys = data.get("CBuys")
        price = data.get("price")
        ticker = hyperliquid_symbol_mapper.get(symbol)

        if not ticker or not leverage or not amount:
            return {"status": "error", "message": f"Invalid or lacking payload"}
        
        ### log the raw received signal
        print(f"writing data {ticker} {event}, {amount}, {price}, {cycleBuys}")
        await writeUnfilteredSignals("hyperliquid", ticker, event, amount, price, cycleBuys)
        print("data written")
        ### Add the dsr checker here, if permission given to buy, buy else exit, or add it under case of buy event, we will see
        print(f"checking event {event}")
        # Case of market buy
        if event == "buy":
            leverage = await bot.setLeverage(leverage=leverage, symbol=ticker)
            order = await bot.leveragedMarketOrder(symbol=ticker, side="Buy", amount=amount)
            if order[0] == None:
                return {"status": "error", "message": "Failed to execute buy order"}
            # Log the order details
            logging.info(f"BUY | Amount: {amount} | Price: {order[0]} | Order ID: {order[1]}")
            return {
                "status": "buy order success", 
                "message": "Buy order executed", 
                "result": [{order[0]}, {order[1]}]
            }
            
        # Case of market close order/ TODO: case of shorting
        elif event == "sell":
            order = await bot.leveragedMarketOrder(symbol=ticker, side="Sell", amount=amount)
            if order[0] == None :
                return {"status": "error", "message": "Failed to execute sell order"}
            # Log the order details
            logging.info(f"SELL | Amount: {amount} | Price: Price: {order[0]} | Order ID: {order[1]}")
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