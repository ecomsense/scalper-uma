window.addEventListener("DOMContentLoaded", () => {
	if (typeof LightweightCharts === 'undefined') {
		console.error('LightweightCharts library not loaded');
		return;
	}

	const chartOptions = {
		layout: { background: { color: "#1a202c" }, textColor: "#d1d4dc" },
		grid: { vertLines: { color: "#2b2b43" }, horzLines: { color: "#2b2b43" } },
		timeScale: { timeVisible: true, secondsVisible: false },
	};

	const candlestickOptions = {
		upColor: "#4CAF50",
		downColor: "#f44336",
		borderVisible: false,
		wickUpColor: "#4CAF50",
		wickDownColor: "#f44336",
	};

	const maColors = { ma1: "#FFA500", ma2: "#00FF00", ma3: "#FF00FF" };

	let chartSettings = { ma_1: null, ma_2: null, ma_3: null, history: 200 };

	function setupChart(containerId, symbol, buttonIds) {
		const chartContainer = document.getElementById(containerId);
		if (!chartContainer) {
			console.error(`Chart container '${containerId}' not found`);
			return;
		}

		const chart = LightweightCharts.createChart(chartContainer, chartOptions);
		const candleSeries = chart.addCandlestickSeries(candlestickOptions);
		const maSeries = {};

		if (chartSettings.ma_1) maSeries.ma1 = chart.addLineSeries({ color: maColors.ma1, lineWidth: 2 });
		if (chartSettings.ma_2) maSeries.ma2 = chart.addLineSeries({ color: maColors.ma2, lineWidth: 2 });
		if (chartSettings.ma_3) maSeries.ma3 = chart.addLineSeries({ color: maColors.ma3, lineWidth: 2 });

		let candleData = [];

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

		function updateMAs() {
			if (maSeries.ma1 && candleData.length >= chartSettings.ma_1) {
				maSeries.ma1.setData(calculateMA(candleData, chartSettings.ma_1));
			}
			if (maSeries.ma2 && candleData.length >= chartSettings.ma_2) {
				maSeries.ma2.setData(calculateMA(candleData, chartSettings.ma_2));
			}
			if (maSeries.ma3 && candleData.length >= chartSettings.ma_3) {
				maSeries.ma3.setData(calculateMA(candleData, chartSettings.ma_3));
			}
		}

		function loadHistorical() {
			return fetch(`/api/historical/${symbol}`)
				.then(r => r.json())
				.then(result => {
					if (result.data && result.data.length > 0) {
						const allData = result.data.reverse();
						candleData = allData.slice(-chartSettings.history);
						candleSeries.setData(candleData);
						updateMAs();
					}
				})
				.catch(e => {
					console.error('Historical error:', e);
				});
		}

		function startLiveUpdates() {
			const es = new EventSource(`/sse/candlesticks/${symbol}`);
			es.addEventListener("live_update", (e) => {
				const d = JSON.parse(e.data);
				const lastTime = candleData.length > 0 ? candleData[candleData.length - 1].time : 0;
				if (d.time > lastTime) {
					candleData.push(d);
					candleSeries.setData(candleData);
				} else if (d.time === lastTime) {
					candleData[candleData.length - 1] = d;
					candleSeries.setData(candleData);
				}
				updateMAs();
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

	fetch("/api/chart/settings")
		.then(r => r.json())
		.then(s => { chartSettings = s; })
		.then(() => fetch("/api/symbols"))
		.then(r => r.json())
		.then(symbols => {
			if (!Array.isArray(symbols) || symbols.length < 2) return;
			document.getElementById("chart-title-CE").textContent = symbols[0];
			setupChart("chart-CE", symbols[0], { high: "buy-btn-CE", mktbuy: "mkt-btn-CE", reset: "sell-btn-CE" });
			document.getElementById("chart-title-PE").textContent = symbols[1];
			setupChart("chart-PE", symbols[1], { high: "buy-btn-PE", mktbuy: "mkt-btn-PE", reset: "sell-btn-PE" });
		});
});
