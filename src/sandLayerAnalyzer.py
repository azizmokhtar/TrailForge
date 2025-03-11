from datetime import datetime, timedelta

class sandLayerAnalyzer:
    def __init__(self, price):
        """Initialize sandLayerAnalyzer with price of first buy."""
        self.price = price
    
    async def linearDcaCalculator(self, numberOfLevels, deviation):
        """Calculate prices for linear dollar-cost averaging strategy."""
        prices = [0] * numberOfLevels
        for i in range(numberOfLevels):
            prices[i] = self.price * (1 - deviation * i)
        return prices
    
    async def calculateTakeProfit(price, target):
        return price + (1 + target)