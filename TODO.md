# TODO - Scalper-UMA

## Next: Replace Toast with Chart Lines

**Goal**: Remove toast notifications for order updates, draw buy/sell line on chart instead.

### Changes Required

#### 1. Frontend: SSE Order Handler (chart.js)

**Current** (lines 312-323):
```javascript
orderSource.addEventListener("order_msg", (e) => {
    const msg = JSON.parse(e.data);
    const status = msg.status || msg.ost || "";
    const validStatuses = ["trigger_pending", "COMPLETE", "OPEN", "PENDING"];
    if (!validStatuses.includes(status)) return;
    
    const isBuy = msg.bs === "B";
    let toastMsg = (isBuy ? "Buy " : "Sell ") + (msg.tsym || "Order");
    showToast(toastMsg, !isBuy);  // <-- REMOVE THIS
});
```

**Replace with**: Draw line on respective chart
```javascript
orderSource.addEventListener("order_msg", (e) => {
    const msg = JSON.parse(e.data);
    const status = msg.status || msg.ost || "";
    const validStatuses = ["trigger_pending", "COMPLETE", "OPEN", "PENDING"];
    if (!validStatuses.includes(status)) return;

    const isBuy = msg.bs === "B";
    const orderSymbol = msg.tsym;
    const price = msg.price || msg.ltp;

    // Match symbol to chart and draw line
    if (orderSymbol === symbols[1]) {
        drawEntryLine(price, isBuy);  // CE chart
    } else if (orderSymbol === symbols[0]) {
        drawEntryLine(price, isBuy);  // PE chart
    }
});
```

**Issues to resolve**:
- Need access to `symbols` array in SSE handler scope
- Need to pass chart's symbol to drawEntryLine

#### 2. Frontend: Entry Button Handlers (chart.js)

**Current** (lines 253-256):
```javascript
clearAllLines();
drawBuyLine(buyPrice);
drawStopLine(stopPrice);      // <-- REMOVE
drawTargetLine(targetPrice);  // <-- REMOVE
```

**Replace with**:
```javascript
clearAllLines();
drawEntryLine(buyPrice, true);  // true = buy (green)
```

Same for mktbuy button (lines 278-281).

#### 3. Frontend: Simplify Line Functions

**Remove** (lines 161-181):
- `drawStopLine()` - DELETE
- `drawTargetLine()` - DELETE

**Replace** `drawBuyLine()` with single `drawEntryLine(price, isBuy)`:
```javascript
function drawEntryLine(price, isBuy) {
    clearAllLines();
    return candleSeries.createPriceLine({
        price: price,
        color: isBuy ? '#4CAF50' : '#f44336',  // green or red
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: isBuy ? 'BUY' : 'SELL',
    });
}
```

#### 4. Implementation Order

1. Add `drawEntryLine()` function (replace drawBuyLine)
2. Modify entry button handlers to only draw one line
3. Modify SSE handler to draw line instead of toast
4. Handle symbol-to-chart matching (CE → CE chart, PE → PE chart)

### Notes

- Current 2 charts: symbols[0]=PE, symbols[1]=CE
- Order msg contains `tsym` (trading symbol)
- Need to match order.tsym to correct chart

---

## Previous: Frontend-Based Trading (On Hold)

See "Frontend-Based Trading (New Architecture)" section (now on hold).

---

## Testing Required (Pre-2016-04-22)

- [ ] Test modify-to-market when target reached after server restart (fix deployed at 14:34)
- [ ] Test complete flow: BUY → exit SL placed → target reached → modify to market → sold

## Bugs to Fix (Pre-2016-04-22)

- [ ] Cron start at 9:14 AM not logging to cron.txt (investigate)
- [ ] M2M calculation verification (customer to confirm)

## Features (Pre-2016-04-22)

- [ ] Add more detailed logging to TickRunner for debugging
- [ ] Unit tests for trade flow

## Cron (Pre-2016-04-22)

- [ ] Verify morning start cron is working correctly
- [ ] Add cron job health check

---

## Notes (Pre-2016-04-22)

- Last tested: 2026-04-21
- Server stops at 15:31 correctly
- Exit SL placement is working
- Modify-to-market needs fresh trade test