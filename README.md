# TrailForge

TrailForge is an API endpoint specifically designed for cryptocurrency trading, starting with HyperLiquid as the initial exchange of choice due to the personal preference of the developer. This project aims to evolve into a robust platform that supports over 100 exchanges, offering users a comprehensive UI to manage accounts and subaccounts seamlessly.

The bot supports only futures and long positions for now, more to be implemeted...

## How to install:

### Prerequisites
- Ubuntu VPS
- Python 3
- Git

### Step 1: Rent a VPS
Rent a VPS from your preferred provider. Ensure it runs Ubuntu.

### Step 2: Initial Setup
Connect to your VPS via SSH and update the system:

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 3: Install Required Software
Install the necessary dependencies:

```bash
sudo apt install -y screen python3 python3-pip git
```

### Step 4: Clone the Repository
Clone the TrailForge repository:

```bash
git clone [repository-url]
cd TrailForge
```

### Step 5: Set Up Python Environment
Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 6: Configure the Bot
Edit the Telegram messenger configuration file:

```bash
cd src
nano telegramMessenger.py
```

Add your API keys where indicated, then save and exit (Ctrl+S, Ctrl+X).

### Step 7: Open a screen for background running
Navigate back to the main directory and open a screen:

```bash
cd ..
screen -S tradingviewListener
```

### Step 8: Launch the Bot
Activate the virtual environemnt and start the bot:

```bash
source venv/bin/activate
python3 -m src.caravanDispatch
```

Follow the prompts to enter your credentials when requested.

### Step 9: Set up trading View
Open trading view and create a pinescript script and paste this code; this will work as a wrapper that is needed for the module truthCompass which eliminates trading view false or duplicate signals (which happen often), it works with dca strategies as well as one entry strategies:
```bash
//@version=5
indicator('PlugHub', overlay=true)

//This function turns whatever function I plug in it to my format of preference
buy = input.source(close, "buy")
sell = input.source(close, "sell")

// Create proper boolean conditions
buyCondition = buy != 0  // Convert to explicit boolean
sellCondition = sell != 0  // Convert to explicit boolean

var int cycleBuys = 0
if buyCondition 
    cycleBuys := cycleBuys + 1
if sellCondition
    cycleBuys := 0

// Export the cycle count as a plotted value that can be referenced in alerts
plot(cycleBuys, "CycleBuys", color.new(color.blue, 100), display=display.none)

alertcondition(buyCondition, 'BUY ASSET', 'CycleBuys: {{cycleBuys}}')
alertcondition(sellCondition, 'SELL ASSET', 'CycleBuys: {{cycleBuys}}')

plotshape(buyCondition, style=shape.triangleup, location=location.bottom, color=color.new(#000000, 0), size=size.tiny, title='Buy')
plotshape(sellCondition, style=shape.triangledown, location=location.top, color=color.new(#000000, 0), size=size.tiny, title='Sell')

```

This script will be the middleman between your strategy and the webhook alert, you just have to link your buy signal to it's appropriate place, and the sell as well, pretty straightforward.

Now moving to the webhook! you will need two alerts, one for buys with this message:
amount must be your position size in dollars, and cycleBuys is the duplicate signal filter input.

```bash
{
    "event": "buy",
    "data": {
        "symbol": "btc",
        "price": "{{close}}",
        "leverage": 3,
        "amount": 20, 
        "time": "{{time}}",
        "cycleBuys": {{plot("CycleBuys")}}
    }
}
```
And one for sells with this message:
the amount here is irrelevant, since the bot will fetch your position size internally.
```bash
{
    "event": "sell",
    "data": {
        "symbol": "btc",
        "price": "{{close}}",
        "leverage": 3,
        "amount": 20, 
        "time": "{{time}}",
        "cycleBuys": {{plot("CycleBuys")}}
    }
}
```
And for the webhook adress: http://YOUR-VPS-IP:80

And you are all set !
## Usage
Once configured, the bot will:
- Receive alerts from your trading view
- Execute trading actions based on received signals
- Forward alerts to your Telegram group, if you want