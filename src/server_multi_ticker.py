from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import asyncio
import logging
from datetime import datetime
from hyperliquid import hyperLiquid 


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
        if symbol == 'btc':
            ticker = "BTC/USDC:USDC"
        elif symbol == 'eth':
            ticker = "ETH/USDC:USDC"
        elif symbol == 'sol':
            ticker = "SOL/USDC:USDC"
        elif symbol == 'xrp':
            ticker = "XRP/USDC:USDC"
        elif symbol == 'sui':
            ticker = "SUI/USDC:USDC"
        if not symbol:
            ticker = ''
            return {"status": "error", "message": "Missing required field: symbol"}

        # Initialize the bot asynchronously
        bot = await hyperLiquid.create()

        # Case of market buy
        if event == "buy":
             # Fetch the current ask price
            ticker_data = await bot.fetchTicker(symbol=ticker)
            if ticker_data and "ask" in ticker_data:
                price = ticker_data["ask"]
                print(f"Price is {price}")
            else:
                return {"status": "error", "message": "Failed to fetch ask price"}

            # Place a buy order
            result = await bot.leveragedMarketOrder(symbol=ticker, side="Buy", amount=amount, price=price)
            order_id = result[1]

            # Log the order details
            logging.info(f"BUY | Amount: {amount} | Price: {price} | Order ID: {order_id}")

            print(result)
            return {"status": "success", "message": "Buy order executed", "result": result}

        # Case of market close order
        elif event == "sell":
            # Fetch the current bid price
            ticker_data = await bot.fetchTicker(symbol=ticker)
            if ticker_data and "bid" in ticker_data:
                price = ticker_data["bid"]
            else:
                return {"status": "error", "message": "Failed to fetch bid price"}

            # Place a sell order
            result = await bot.leveragedMarketOrder(symbol=ticker, side="Sell", amount=amount, price=price)
            order_id = result[1]

            # Log the order details
            logging.info(f"SELL | Amount: {amount} | Price: {price} | Order ID: {order_id}")

            return {"status": "success", "message": "Sell order executed", "result": result}

        else:
            return {"status": "error", "message": f"Unknown event: {event}"}

    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)  # Run on port 80

