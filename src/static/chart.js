window.addEventListener("DOMContentLoaded", () => {
	if (typeof LightweightCharts === 'undefined') {
		console.error('LightweightCharts library not loaded');
		return;
	}

	window.updatePositionsSummary = function() {
		fetch("/api/positions/summary")
			.then(r => r.json())
			.then(data => {
				const orderCount = data.order_count || 0;
				const positionCount = data.position_count || 0;
				const realizedPnl = data.realized_pnl || 0;

				// Always show if we have activity (orders OR positions OR realized pnl)
				if (orderCount === 0 && positionCount === 0 && realizedPnl === 0) {
					// No activity at all - skip this update
					return;
				}

				document.getElementById("pos-count").textContent = positionCount;
				document.getElementById("order-count").textContent = (data.active_orders || 0) + "/" + orderCount;
				const m2mEl = document.getElementById("m2m");
				const realEl = document.getElementById("realized");
				m2mEl.textContent = (data.m2m || 0).toFixed(2);
				realEl.textContent = realizedPnl.toFixed(2);
				m2mEl.parentElement.classList.toggle("negative", data.m2m < 0);
				realEl.parentElement.classList.toggle("negative", realizedPnl < 0);
			})
			.catch(console.error);
	};

	const chartOptions = {
		layout: { background: { color: "#1a202c" }, textColor: "#d1d4dc" },
		grid: { vertLines: { color: "#2b2b43" }, horzLines: { color: "#2b2b43" } },
		crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
		localization: {
			timeFormatter: (time) => {
				const date = new Date(time * 1000);
				return date.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });
			},
		},
		timeScale: { 
			timeVisible: true, 
			secondsVisible: false,
			tickMarkFormatter: (time) => {
				const date = new Date(time * 1000);
				return date.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });
			},
			rightMargin: 10,
		},
		priceScale: {
			rightMargin: 10,
		},
	};

	const candlestickOptions = {
		upColor: "#4CAF50",
		downColor: "#f44336",
		borderVisible: false,
		wickUpColor: "#4CAF50",
		wickDownColor: "#f44336",
	};

	const maColors = ["#FFA500", "#00FF00", "#FF00FF", "#00FFFF", "#FF00AA", "#FFFF00"];

	function calculateSMA(data, period, priceField) {
		const result = [];
		for (let i = period - 1; i < data.length; i++) {
			let sum = 0;
			for (let j = 0; j < period; j++) {
				sum += data[i - j][priceField];
			}
			result.push({ time: data[i].time, value: sum / period });
		}
		return result;
	}

	function calculateEMA(data, period, priceField) {
		const result = [];
		const multiplier = 2 / (period + 1);
		let ema = null;
		
		for (let i = 0; i < data.length; i++) {
			const price = data[i][priceField];
			if (i < period - 1) {
				continue;
			} else if (i === period - 1) {
				let sum = 0;
				for (let j = 0; j < period; j++) {
					sum += data[j][priceField];
				}
				ema = sum / period;
			} else {
				ema = (price - ema) * multiplier + ema;
			}
			result.push({ time: data[i].time, value: ema });
		}
		return result;
	}

	function setupChart(containerId, symbol, buttonIds, settings) {
		const chartContainer = document.getElementById(containerId);
		if (!chartContainer) return;

		const profit = settings?.profit || 5;

		const chart = LightweightCharts.createChart(chartContainer, chartOptions);
		const candleSeries = chart.addCandlestickSeries(candlestickOptions);
		
		// OHLC display
		const ohlcDiv = document.createElement('div');
		ohlcDiv.style.cssText = 'position:absolute;top:30px;left:10px;background:#1a202c;color:#d1d4dc;padding:4px 8px;font-size:12px;pointer-events:none;z-index:10;';
		chartContainer.style.position = 'relative';
		chartContainer.appendChild(ohlcDiv);
		
		chart.subscribeCrosshairMove((param) => {
			if (param.time && param.seriesData.get(candleSeries)) {
				const data = param.seriesData.get(candleSeries);
				ohlcDiv.textContent = `O:${data.open} H:${data.high} L:${data.low} C:${data.close}`;
			} else {
				ohlcDiv.textContent = '';
			}
		});
		
		const maConfigs = settings && settings.ma ? settings.ma : [];
		const maSeries = [];
		
		maConfigs.forEach((config, index) => {
			const color = maColors[index % maColors.length];
			const series = chart.addLineSeries({ 
				color: color, 
				lineWidth: 1,
				lastValueVisible: false,
				crosshairMarkerVisible: false,
			});
			maSeries.push({ series, config });
		});

		// Price line for buy/sell entry - single line replaces previous
		let entryLine = null;
		function clearAllLines() {
			if (entryLine) { 
				try { candleSeries.removePriceLine(entryLine); } catch(e) {} 
				entryLine = null; 
			}
		}

		function drawEntryLine(price, isBuy) {
			clearAllLines();
			entryLine = candleSeries.createPriceLine({
				price: price,
				color: isBuy ? '#4CAF50' : '#f44336',
				lineWidth: 2,
				lineStyle: 2,
				axisLabelVisible: true,
				title: isBuy ? 'BUY' : 'SELL',
			});
		}

		// Expose drawEntryLine globally for SSE handler
		window.chartFunctions = window.chartFunctions || {};
		window.chartFunctions[symbol] = drawEntryLine;

		// Remove test lines - will draw when trade placed
		// window.drawEntryLine(50, true);

		let candleData = [];

		function updateMAs() {
			maSeries.forEach(({ series, config }) => {
				const period = config.period;
				const priceField = config.price || 'close';
				const type = config.type || 'sma';
				
				if (candleData.length < period) return;
				
				const data = type === 'ema' 
					? calculateEMA(candleData, period, priceField)
					: calculateSMA(candleData, period, priceField);
				
				series.setData(data);
			});
		}

		function loadHistorical() {
			return fetch(`/api/historical/${symbol}`)
				.then(r => r.json())
				.then(result => {
					if (result.data && result.data.length > 0) {
						candleData = result.data.reverse();
						candleSeries.setData(candleData);
						updateMAs();
					}
				})
				.catch(e => console.error('Historical error:', e));
		}

		function startLiveUpdates() {
			const es = new EventSource(`/sse/candlesticks/${symbol}`);
			es.addEventListener("live_update", (e) => {
				const candle = JSON.parse(e.data);
				if (candleData.length === 0) return;
				const lastCandle = candleData[candleData.length - 1];
				
				if (candle.time === lastCandle.time) {
					lastCandle.high = candle.high;
					lastCandle.low = candle.low;
					lastCandle.close = candle.close;
					candleSeries.update(lastCandle);
				} else if (candle.time > lastCandle.time) {
					candleData.push(candle);
					candleSeries.update(candle);
					updateMAs();
				}
			});
		}

		loadHistorical().then(() => startLiveUpdates());

		document.getElementById(buttonIds.high).onclick = () => {
			const candles = candleSeries.data();
			if (candles.length < 2) {
				showToast("Need at least 2 candles to place order", true);
				return;
			}
			const curr = candles[candles.length - 1];
			const prev = candles[candles.length - 2];
			const ltp = curr.close;
			const buyPrice = prev.high + 0.05;
			const stopPrice = prev.low;
			const targetPrice = buyPrice + profit;
			clearAllLines();
			fetch("/api/trade/buy", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					symbol, ltp, price: prev.high + 0.05, trigger_price: prev.high,
					order_type: "SL", exit_price: prev.low, cost_price: prev.high + 0.05
				})
			});
		};

		document.getElementById(buttonIds.mktbuy).onclick = () => {
			const candles = candleSeries.data();
			if (candles.length < 2) {
				showToast("Need at least 2 candles to place order", true);
				return;
			}
			const curr = candles[candles.length - 1];
			const prev = candles[candles.length - 2];
			const buyPrice = curr.close + 2;
			const stopPrice = prev.low;
			const targetPrice = buyPrice + profit;
			clearAllLines();
			fetch("/api/trade/buy", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					symbol, ltp: curr.close, price: curr.close + 2, order_type: "LMT",
					exit_price: prev.low, cost_price: curr.close + 0.05
				})
			}).then(r => r.json()).then(data => {
				if (data.order && data.order.entry_id) {
					showToast("Cleaned up other orders", false);
				}
			});
		};

		document.getElementById(buttonIds.reset).onclick = () => {
			clearAllLines();
			fetch(`/api/trade/sell?symbol=${encodeURIComponent(symbol)}`, { method: "GET" });
		};
	}

	fetch("/api/chart/settings")
		.then(r => r.json())
		.then(settings => {
			return fetch("/api/symbols").then(r => r.json()).then(symbols => ({ settings, symbols }));
		})
.then(({ settings, symbols }) => {
			if (!Array.isArray(symbols) || symbols.length < 2) return;

			const orderSource = new EventSource("/sse/orders");
			setInterval(updatePositionsSummary, 5000);
			orderSource.addEventListener("order_msg", (e) => {
				try {
					const msg = JSON.parse(e.data);
					const status = msg.status || msg.ost || "";
					const validStatuses = ["trigger_pending", "COMPLETE", "OPEN", "PENDING"];
					if (!validStatuses.includes(status)) return;

					const isBuy = msg.bs === "B";
					const orderSymbol = msg.tsym;
					const price = msg.price || msg.ltp;

					// Show toast for SSE order update (fallback since lines aren't working)
					showToast((isBuy ? "BUY" : "SELL") + " " + orderSymbol + " @ " + price, false);

					// Try to draw entry line on matching chart
					if (window.chartFunctions && window.chartFunctions[orderSymbol]) {
						window.chartFunctions[orderSymbol](price, isBuy);
					}
				} catch (err) { console.error("Order msg parse error:", err); }
			});

			document.getElementById("chart-title-CE").textContent = symbols[1];
			setupChart("chart-CE", symbols[1], { high: "buy-btn-CE", mktbuy: "mkt-btn-CE", reset: "sell-btn-CE" }, settings);
			document.getElementById("chart-title-PE").textContent = symbols[0];
			setupChart("chart-PE", symbols[0], { high: "buy-btn-PE", mktbuy: "mkt-btn-PE", reset: "sell-btn-PE" }, settings);

			updatePositionsSummary();
		});
});
