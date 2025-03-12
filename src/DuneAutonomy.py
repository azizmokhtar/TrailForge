"""
Basic logic:
- If not in pos:
    enter a position
    set first take profit limit
    calculate dca levels and enter them as limit
    

- If in pos:
    If we hit tp:
        return reset the loop
    If price < dca limit order:
        check if limit order hit (position size grew)
    If limit orders hit > first batch of limit orders:
        create new ones based on some logic
"""