from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel
import logging
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
        amount = 15  # Fixed amount for simplicity
        ticker = hyperliquid_symbol_mapper.get(symbol)
        
        if not ticker:
            return {"status": "error", "message": f"Invalid or missing symbol: {symbol}"}
            
        # Case of market buy
        if event == "buy":
            # Properly await the coroutine to get the result
            buy_price, order_id = await bot.leveragedMarketOrder(symbol=ticker, side="Buy", amount=amount)
            
            if buy_price is None or order_id is None:
                return {"status": "error", "message": "Failed to execute buy order"}
                
            # Log the order details
            logging.info(f"BUY | Amount: {amount} | Price: {buy_price} | Order ID: {order_id}")
            return {
                "status": "buy order success", 
                "message": "Buy order executed", 
                "result": [buy_price, order_id]
            }
            
        # Case of market close order
        elif event == "sell":
            # Properly await the coroutine to get the result
            sell_price, order_id = await bot.leveragedMarketOrder(symbol=ticker, side="Sell", amount=amount)
            
            if sell_price is None or order_id is None:
                return {"status": "error", "message": "Failed to execute sell order"}
                
            # Log the order details
            logging.info(f"SELL | Amount: {amount} | Price: {sell_price} | Order ID: {order_id}")
            return {
                "status": "sell order success", 
                "message": "Sell order executed", 
                "result": [sell_price, order_id]
            }
            
        else:
            return {"status": "error", "message": f"Unknown event: {event}"}
            
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)  # Run on port 80