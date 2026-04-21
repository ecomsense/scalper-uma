# TODO - Scalper-UMA

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

## Notes

- Last tested: 2026-04-21
- Server stops at 15:31 correctly
- Exit SL placement is working
- Modify-to-market needs fresh trade test
