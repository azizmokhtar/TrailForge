from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import logging
from datetime import datetime
from hyperliquid import hyperLiquid 
from config.hyperliquid_symbol_map import hyperliquid_symbol_mapper 


# Initialize FastAPI app
app = FastAPI()

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

        # Initialize the bot asynchronously
        bot = await hyperLiquid.create()

        # Case of market buy
        if event == "buy":
            # Place a buy order
            result = await bot.leveragedMarketOrder(symbol=ticker, side="Buy", amount=amount)
            # Log the order details
            logging.info(f"BUY | Amount: {amount} | Price: {result[0]} | Order ID: {result[1]}")
            return {"status": "success", "message": "Buy order executed", "result": result}

        # Case of market close order
        elif event == "sell":
            # Place a sell order
            result = await bot.leveragedMarketOrder(symbol=ticker, side="Sell", amount=amount)
            # Log the order details
            logging.info(f"SELL | Amount: {amount} | Price: {result[0]} | Order ID: {result[1]}")
            return {"status": "success", "message": "Sell order executed", "result": result}

        else:
            return {"status": "error", "message": f"Unknown event: {event}"}

    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)  # Run on port 80

