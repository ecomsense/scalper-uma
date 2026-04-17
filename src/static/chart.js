window.addEventListener("DOMContentLoaded", () => {
	if (typeof LightweightCharts === 'undefined') {
		console.error('LightweightCharts library not loaded');
		return;
	}

	const chartOptions = {
		layout: { background: { color: "#1a202c" }, textColor: "#d1d4dc" },
		grid: { vertLines: { color: "#2b2b43" }, horzLines: { color: "#2b2b43" } },
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
		},
	};

	const candlestickOptions = {
		upColor: "#4CAF50",
		downColor: "#f44336",
		borderVisible: false,
		wickUpColor: "#4CAF50",
		wickDownColor: "#f44336",
	};

	const maColors = { ma1: "#FFA500", ma2: "#00FF00", ma3: "#FF00FF" };

	function calculateMA(data, period) {
		const result = [];
		for (let i = period - 1; i < data.length; i++) {
			let sum = 0;
			for (let j = 0; j < period; j++) {
				sum += data[i - j].close;
			}
			result.push({ time: data[i].time, value: sum / period });
		}
		return result;
	}

	function setupChart(containerId, symbol, buttonIds, settings) {
		const chartContainer = document.getElementById(containerId);
		if (!chartContainer) return;

		const chart = LightweightCharts.createChart(chartContainer, chartOptions);
		const candleSeries = chart.addCandlestickSeries(candlestickOptions);
		
		let ma1Series = null, ma2Series = null, ma3Series = null;
		
		if (settings && settings.ma_1) {
			ma1Series = chart.addLineSeries({ color: maColors.ma1, lineWidth: 2 });
		}
		if (settings && settings.ma_2) {
			ma2Series = chart.addLineSeries({ color: maColors.ma2, lineWidth: 2 });
		}
		if (settings && settings.ma_3) {
			ma3Series = chart.addLineSeries({ color: maColors.ma3, lineWidth: 2 });
		}

		let candleData = [];

		function updateMAs() {
			if (ma1Series && settings && candleData.length >= settings.ma_1) {
				ma1Series.setData(calculateMA(candleData, settings.ma_1));
			}
			if (ma2Series && settings && candleData.length >= settings.ma_2) {
				ma2Series.setData(calculateMA(candleData, settings.ma_2));
			}
			if (ma3Series && settings && candleData.length >= settings.ma_3) {
				ma3Series.setData(calculateMA(candleData, settings.ma_3));
			}
		}

		function loadHistorical() {
			return fetch(`/api/historical/${symbol}`)
				.then(r => r.json())
				.then(result => {
					if (result.data && result.data.length > 0) {
						const reversed = result.data.reverse();
						const keepCount = (settings && settings.history) ? settings.history : 200;
						candleData = reversed.slice(-keepCount);
						candleSeries.setData(candleData);
						updateMAs();
					}
				})
				.catch(e => console.error('Historical error:', e));
		}

		function startLiveUpdates() {
			const es = new EventSource(`/sse/candlesticks/${symbol}`);
			es.addEventListener("live_update", (e) => {
				const d = JSON.parse(e.data);
				if (candleData.length > 0 && d.time === candleData[candleData.length - 1].time) {
					candleData[candleData.length - 1] = d;
					candleSeries.update(d);
					updateMAs();
				}
			});
			es.onerror = () => console.log('SSE disconnected');
		}

		loadHistorical().then(() => startLiveUpdates());

		document.getElementById(buttonIds.high).onclick = () => {
			const candles = candleSeries.data();
			if (candles.length < 2) return;
			const prev = candles[candles.length - 2];
			fetch("/api/trade/buy", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					symbol, price: prev.high + 0.05, trigger_price: prev.high,
					order_type: "SL", exit_price: prev.low, cost_price: prev.high + 0.05
				})
			});
		};

		document.getElementById(buttonIds.mktbuy).onclick = () => {
			const candles = candleSeries.data();
			if (candles.length < 2) return;
			const curr = candles[candles.length - 1];
			const prev = candles[candles.length - 2];
			fetch("/api/trade/buy", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					symbol, price: curr.close + 2, order_type: "LIMIT",
					exit_price: prev.low, cost_price: curr.close + 0.05
				})
			});
		};

		document.getElementById(buttonIds.reset).onclick = () => {
			fetch("/api/trade/sell", { method: "GET" });
		};
	}

	// Fetch settings first, then symbols, then setup charts
	fetch("/api/chart/settings")
		.then(r => r.json())
		.then(settings => {
			console.log('Chart settings loaded:', settings);
			return fetch("/api/symbols").then(r => r.json()).then(symbols => ({ settings, symbols }));
		})
		.then(({ settings, symbols }) => {
			if (!Array.isArray(symbols) || symbols.length < 2) return;
			document.getElementById("chart-title-CE").textContent = symbols[0];
			setupChart("chart-CE", symbols[0], { high: "buy-btn-CE", mktbuy: "mkt-btn-CE", reset: "sell-btn-CE" }, settings);
			document.getElementById("chart-title-PE").textContent = symbols[1];
			setupChart("chart-PE", symbols[1], { high: "buy-btn-PE", mktbuy: "mkt-btn-PE", reset: "sell-btn-PE" }, settings);
		});
});
