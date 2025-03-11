#====================================================================================================
# caravanDispatch is a module of TrailForge that takes care specifically of trading following tradingview signals.
# Starting with market orders execution for fast in and out of the market movements; it will give option to benefit of the upcoming module "sandLayerAnalyzer" in the future.
# caravanDispatch now only takes care of buy signalling, there will be also an appropriate modular symmetric version for shrting purposes with the same functionalities. 
# sandLayerAnalyzer will take care of buy lots layering and tp calculations.
#====================================================================================================

from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel
import logging
import asyncio
from src.hyperliquid import hyperLiquid
from src.sandLayerAnalyzer import sandLayerAnalyzer
from src.truthCompass import truthCompass
from config.hyperliquid_symbol_map import hyperliquid_symbol_mapper

# Global bot instance that will be initialized at startup
bot = None
filter = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the bot
    global bot
    print("Initializing trading bot...")
    # Create the bot instance and prompt for credentials
    bot = await hyperLiquid.create()
    print("Bot successfully initialized and ready to receive trading signals.")
    
    yield  # This is where FastAPI serves requests
    
    print("Shutting down trading bot...")
    # TODO: any cleanup code here if needed

app = FastAPI(lifespan=lifespan)

# logger configs for both executed orders and also alerts ( raw and filtered )
def orderLogger(symbol, side, amount, price, order_id):
    # Create a file path for this cryptocurrency
    logFile = f"logs/executed_{symbol.lower()}.log"
    # Create a simple message to log
    timestamp = logging.Formatter('%(asctime)s', '%Y-%m-%d %H:%M:%S').format(logging.LogRecord('', 0, '', 0, '', '', None))
    logMessage = f"{timestamp} - SIDE: {side} | Amount: {amount} | Price: {price} | Order ID: {order_id}\n"
    # Write directly to the file
    with open(logFile, 'a') as f:
        f.write(logMessage)

def alertLogger(type, symbol, side, amount, price, cycleBuy):
    logFile = f"logs/{type.lower()}_{symbol.lower()}_signal.log"
    timestamp = logging.Formatter('%(asctime)s', '%Y-%m-%d %H:%M:%S').format(logging.LogRecord('', 0, '', 0, '', '', None))
    logMessage = f"{timestamp} - Symbol: {symbol} | Side: {side} | Amount: {amount} | Price: {price} | Buy number: {cycleBuy}\n"
    # Write directly to the file
    with open(logFile, 'a') as f:
        f.write(logMessage)

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
        ticker = hyperliquid_symbol_mapper.get(symbol)
        amount = int(data.get("amount"))  # can be dynamic, as long as > 11 dollars
        leverage = int(data.get("leverage"))
        price = float(data.get("price"))
        cycleBuy = int(data.get("cycleBuys"))

        if not ticker or not leverage or not amount:
            return {"status": "error", "message": f"Invalid or lacking payload"}
        
        # Run all truthCompass operations in a thread pool
        def process_signal():
            tracker = truthCompass(symbol)
            tracker.addNewSignal("raw", symbol, event, price, cycleBuy)
            tracker.save()
            return tracker.checkAndUpdate(symbol, event, price, cycleBuy)

        checker = await asyncio.to_thread(process_signal)
        
        print(f"checking event {event}")
        # Case of market buy
        if event == "buy" and checker == 0:
            if cycleBuy == 1:
                leverage = await bot.setLeverage(leverage, ticker)
                order = await bot.leveragedMarketOrder(ticker, "Buy", amount)
                if order[0] == None:
                    return {"status": "error", "message": "Failed to execute buy order"}
                # Log the order details
                buyPrice = order [0]
                # calculate and execute dca limit orders
                dcaCalculator = sandLayerAnalyzer(buyPrice)
                dcaLevels = dcaCalculator.linearDcaCalculator(12, 1)
                limitOrderExecution = await bot.createLimitBuyOrders(ticker, dcaLevels, amount)
                if limitOrderExecution == 0:
                    return {"status": "error", "message": "Failed to execute limit dca orders"}
            if cycleBuy > 12:
                order = await bot.leveragedMarketOrder(ticker, "Buy", amount)
                if order[0] == None:
                    return {"status": "error", "message": "Failed to execute buy order"}

            # I will leave the sell order to market for better execution of TTP (TTP calculations happen on tradingview, for now..)
            # TODO: GO over to hyperliquid class and add a function that places limit orders over a loop
            orderLogger(symbol, "BUY", amount, order[0], order[1])
            return {"status": "buy order success", "message": "Buy order executed", "result": [{order[0]}, {order[1]}]}
            
        # Case of market close order/ TODO: case of shorting.. after time thinking , this will be maybe implemented in another script, maybe to run only shorts with stop losses since "dumps have bottoms, but pumps have no ceiling..."
        elif event == "sell" and checker == 0:
            order = await bot.leveragedMarketCloseOrder(ticker, "buy", amount)
            if order[0] == None :
                return {"status": "error", "message": "Failed to execute sell order"}
            # Log the order details
            orderLogger(symbol, "SELL", amount, order[0], order[1])
            return {"status": "sell order success", "message": "Sell order executed", "result": [{order[0]}, {order[1]}]}       
            
        else:
            return {"status": "error", "message": f"Unknown event: {event}"}
            
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)  # Run on port 80