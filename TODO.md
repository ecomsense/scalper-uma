# TODO - Scalper-UMA

## 🚨 MAJOR MILESTONE: Frontend-Based Trading

**This is a major architectural change. May need to revert.**

See "Frontend-Based Trading (New Architecture)" section below.

---

## Testing Required

- [ ] Test modify-to-market when target reached after server restart (fix deployed at 14:34)
- [ ] Test complete flow: BUY → exit SL placed → target reached → modify to market → sold

## Bugs to Fix

- [ ] Cron start at 9:14 AM not logging to cron.txt (investigate)
- [ ] M2M calculation verification (customer to confirm)

## Features

- [ ] Add more detailed logging to TickRunner for debugging
- [ ] Unit tests for trade flow

## Cron

- [ ] Verify morning start cron is working correctly
- [ ] Add cron job health check

## Frontend-Based Trading (New Architecture)

### Goal
Move trade execution logic from backend (TickRunner) to frontend. Frontend already receives live prices via SSE, so it can monitor and execute trades locally.

### Implementation Plan

#### Phase 1: Draw Target & Stop Loss Lines on Chart
- [ ] Add API endpoint `/api/trade/current` to return active trade info (symbol, target_price, exit_price, quantity)
- [ ] Modify chart.js to:
  - Store target_price and exit_price when buy order is placed
  - Draw horizontal line at target_price (green, dashed)
  - Draw horizontal line at exit_price/stop (red, dashed)
  - Use lightweight-charts `createPriceLine()` API
  - Remove lines when trade is closed

#### Phase 2: Monitor Buy Order Execution
- [ ] Frontend listens to SSE `/sse/orders` for order status updates
- [ ] When buy order status = "COMPLETE", then:
  - SL order already placed by backend (current behavior)
  - Draw the target/stop lines
- [ ] When buy order status = "CANCELED" or "REJECTED":
  - Remove any drawn lines

#### Phase 3: Breach Detection on Frontend
- [ ] In SSE `live_update` handler for candlestick:
  - Compare close price with stored target_price and exit_price
  - If close >= target_price: show green toast "Target reached!", remove lines
  - If close <= exit_price: show red toast "Stop loss hit!", remove lines
- [ ] This detection happens purely on frontend - no backend needed

#### Phase 4: Remove TickRunner (Final Goal)
- [ ] Once frontend-based trading is verified working:
  - Remove TickRunner from backend entirely
  - Backend only handles: order placement, order status, positions
  - Frontend handles: price monitoring, target/stop detection, alerts

### Why Frontend-Based Trading?
- Frontend already receives live prices via SSE
- No need for backend to poll/manage state
- Simpler architecture
- Easier to debug (all logic visible in browser console)

### Trade Flow (New)
1. User clicks BUY → Frontend sends to backend
2. Backend places order → returns order_id
3. Frontend monitors SSE for order COMPLETE
4. On COMPLETE: draw target/stop lines
5. Frontend monitors live price via SSE
6. On target/stop breach: show toast, notify backend to close
7. On trade closed: remove lines

## Notes

- Last tested: 2026-04-21
- Server stops at 15:31 correctly
- Exit SL placement is working
- Modify-to-market needs fresh trade test
