# Scalper-UMA: Project Analysis & Improvements

## Project Summary
A real-time options trading bot built with FastAPI that:
- Connects to Finvasia broker API
- Uses WebSocket for live price feeds
- Implements a state machine for entry/exit logic
- Provides SSE endpoints for candlesticks and order streaming
- Currently trades NIFTY options based on premium proximity

---

## Suggested Improvements

### 1. Architecture & Code Structure

| Issue | Location | Suggestion |
|-------|----------|------------|
| No type hints | Throughout codebase | Add type hints using Python 3.10+ syntax |
| Global mutable state | `src/api.py:33-34` (`_api`, `_orders`) | Not thread-safe; use dependency injection or context vars |
| Business logic in routes | `src/main.py:181-228` | Extract to service layer classes |
| No config validation | `src/constants.py` | Add Pydantic models for settings validation |
| No data classes | Various dicts | Use dataclasses or attrs for order_details, settings |

### 2. Performance

| Issue | Location | Suggestion |
|-------|----------|------------|
| Repeated CSV reads | `src/symbol.py` multiple methods | Cache CSV in memory using `@cache` or `lru_cache` |
| Polling for LTP | `src/tickrunner.py:109` | Use event-driven updates instead of fixed 0.5s sleep |
| SSE fixed sleep | `src/main.py:253` | Push updates only when data changes |
| No connection pooling | `src/api.py` | Pool broker API connections if applicable |

### 3. Error Handling

| Issue | Location | Suggestion |
|-------|----------|------------|
| Bare except clauses | Multiple locations | Catch specific exceptions |
| No retry logic | API/WS calls | Add retry with exponential backoff |
| No circuit breaker | Broker API calls | Implement for resilience |
| Mixed logging | `logging.info` + `print` | Standardize on logger |

### 4. Security

| Issue | Location | Suggestion |
|-------|----------|------------|
| Credentials in YAML | `data/settings.yml` | Use environment variables |
| No input validation | API endpoints | Add Pydantic models |
| No rate limiting | All endpoints | Add slowapi |
| Sensitive data in logs | Throughout | Sanitize order IDs, prices |

### 5. Reliability

| Issue | Location | Suggestion |
|-------|----------|------------|
| No health checks | Missing | Add `/health`, `/ready` endpoints |
| Shutdown could be cleaner | `src/main.py:146-155` | Add timeout, force kill |
| No WS reconnection | `src/wserver.py` | Auto-reconnect on disconnect |
| Failed orders | No DLQ | Add dead letter queue |

### 6. Testing

| Issue | Location | Suggestion |
|-------|----------|------------|
| No tests | Missing | Add pytest suite |
| No mocks | - | Add unittest.mock for broker API |
| No integration tests | API routes | Add test client tests |

### 7. Observability

| Issue | Location | Suggestion |
|-------|----------|------------|
| Print-based logging | Throughout | Use structured JSON logging |
| No metrics | Missing | Add Prometheus endpoint |
| No tracing | - | Add correlation IDs for requests |
| No alerts | - | Add webhooks for critical events |

### 8. Configuration

| Issue | Location | Suggestion |
|-------|----------|------------|
| Hardcoded params | `src/constants.py:119-133` | Make configurable via API |
| Single instrument | NIFTY only | Add multi-instrument support |
| No env config | - | Add dev/staging/prod envs |

### 9. Code Quality

| Issue | Location | Suggestion |
|-------|----------|------------|
| Large functions | `run_state_machine`, `lifespan` | Refactor into smaller units |
| Missing docstrings | Most functions | Add for public APIs |
| Naming inconsistencies | Mixed styles | Use snake_case throughout |

### 10. Bugs & Minor Issues

| Issue | Location | Fix |
|-------|----------|-----|
| Early return in get_orders | `src/api.py:64` | Returns on first COMPLETE - likely bug |
| Hardcoded sleep intervals | Multiple | Make configurable |
| Stale data risk | `find_trading_symbol_by_atm` | Add WS disconnect check |

---

## Priority Recommendations

### High Priority
1. Add input validation (Pydantic) - security risk
2. Fix `Helper.get_orders()` bug - potential data loss
3. Add health check endpoints - operational visibility
4. Implement circuit breaker - resilience
5. Add retry logic for API calls - reliability

### Medium Priority
6. Cache CSV file reads - performance
7. Add structured logging - observability
8. Add rate limiting - security
9. Add proper error handling - stability
10. Add environment-based config - deployability

### Low Priority
11. Add type hints throughout - maintainability
12. Write tests - confidence
13. Add Prometheus metrics - monitoring
14. Refactor large functions - readability
15. Add correlation IDs - tracing