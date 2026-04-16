window.addEventListener("DOMContentLoaded", () => {
	const chartOptions = {
		layout: {
			background: { type: "solid", color: "#1a202c" },
			textColor: "#d1d4dc",
		},
		grid: {
			vertLines: { color: "#2b2b43" },
			horzLines: { color: "#2b2b43" },
		},
		timeScale: {
			borderColor: "#48587b",
			timeVisible: true,
			secondsVisible: false,
		},
		rightPriceScale: {
			borderColor: "#48587b",
		},
	};

	const candlestickOptions = {
		upColor: "#4CAF50",
		downColor: "#f44336",
		borderVisible: false,
		wickUpColor: "#4CAF50",
		wickDownColor: "#f44336",
	};

	const maColors = {
		ma1: "#FFA500",
		ma2: "#00FF00",
		ma3: "#FF00FF",
	};

	function setupChart(containerId, symbol, buttonIds) {
		const chartContainer = document.getElementById(containerId);
		if (!chartContainer) {
			console.error(`Chart container with ID '${containerId}' not found.`);
			return;
		}

		const chart = LightweightCharts.createChart(chartContainer, chartOptions);
		const candlestickSeries = chart.addCandlestickSeries(candlestickOptions);
		const ma1Series = chart.addLineSeries({ color: maColors.ma1, lineWidth: 2 });
		const ma2Series = chart.addLineSeries({ color: maColors.ma2, lineWidth: 2 });
		const ma3Series = chart.addLineSeries({ color: maColors.ma3, lineWidth: 2 });

		chart.timeScale().applyOptions({
			timeZone: "Asia/Kolkata",
		});

		let candleData = [];

		function calculateMA(data, period) {
			const maData = [];
			for (let i = period - 1; i < data.length; i++) {
				let sum = 0;
				for (let j = 0; j < period; j++) {
					sum += data[i - j].close;
				}
				maData.push({
					time: data[i].time,
					value: sum / period,
				});
			}
			return maData;
		}

		function updateAllMA() {
			if (candleData.length >= 20) {
				ma1Series.setData(calculateMA(candleData, 20));
			}
			if (candleData.length >= 50) {
				ma2Series.setData(calculateMA(candleData, 50));
			}
			if (candleData.length >= 100) {
				ma3Series.setData(calculateMA(candleData, 100));
			}
			if (candleData.length === 0) {
				ma1Series.setData([]);
				ma2Series.setData([]);
				ma3Series.setData([]);
			}
		}

		function loadHistoricalData() {
			return fetch(`/api/historical/${symbol}`)
				.then((response) => response.json())
				.then((result) => {
					if (result.data && result.data.length > 0) {
						candleData = result.data;
						candlestickSeries.setData(candleData);
						updateAllMA();
						chart.timeScale().fitContent();
						return true;
					}
					return false;
				})
				.catch((error) => {
					console.error("Error loading historical data:", error);
					return false;
				});
		}

		function startLiveUpdates() {
			const candleEventSource = new EventSource(`/sse/candlesticks/${symbol}`);
			let lastTime = null;

			candleEventSource.addEventListener("live_update", (event) => {
				const data = JSON.parse(event.data);
				
				if (lastTime === null || data.time > lastTime) {
					if (candleData.length > 0 && candleData[candleData.length - 1].time === lastTime) {
						candleData[candleData.length - 1] = data;
					} else {
						candleData.push(data);
					}
					lastTime = data.time;
					candlestickSeries.setData(candleData);
				}
				updateAllMA();
			});

			candleEventSource.onerror = (error) => {
				console.error(`SSE disconnected, reconnecting...`);
				setTimeout(() => startLiveUpdates(), 3000);
				candleEventSource.close();
			};
		}

		loadHistoricalData().then((hasHistorical) => {
			if (!hasHistorical) {
				candleData = [];
			}
			startLiveUpdates();
		});

		const tradeLogic = async (endpoint, payload = null) => {
			try {
				const options = {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: payload ? JSON.stringify(payload) : null,
				};
				const response = await fetch(endpoint, options);
				const result = await response.json();
				if (result.status !== "success") {
					alert(`Order failed for ${symbol}.`);
				}
			} catch (error) {
				console.error(`Order failed for ${symbol}:`, error);
				alert(`Order failed for ${symbol}.`);
			}
		};

		document.getElementById(buttonIds.high).onclick = async () => {
			const candles = candlestickSeries.data();
			if (candles.length < 2) return;
			const prevCandle = candles[candles.length - 2];
			const payload = {
				symbol: symbol,
				price: prevCandle.high + 0.05,
				trigger_price: prevCandle.high,
				order_type: "SL",
				exit_price: prevCandle.low,
				cost_price: prevCandle.high + 0.05,
			};
			tradeLogic("/api/trade/buy", payload);
		};

		document.getElementById(buttonIds.mktbuy).onclick = async () => {
			const candles = candlestickSeries.data();
			if (candles.length < 2) return;
			const currCandle = candles[candles.length - 1];
			const prevCandle = candles[candles.length - 2];
			const payload = {
				symbol: symbol,
				price: currCandle.close + 2,
				order_type: "LIMIT",
				exit_price: prevCandle.low,
				cost_price: currCandle.close + 0.05,
			};
			tradeLogic("/api/trade/buy", payload);
		};

		document.getElementById(buttonIds.reset).onclick = async () => {
			try {
				const response = await fetch("/api/trade/sell", { method: "GET" });
				const result = await response.json();
				if (result.status !== "success") {
					alert("Reset failed.");
				}
			} catch (error) {
				console.error("Reset failed:", error);
				alert("Reset failed.");
			}
		};
	}

	async function initCharts() {
		try {
			const response = await fetch("/api/symbols");
			const symbols = await response.json();

			if (!Array.isArray(symbols) || symbols.length < 2) {
				console.error("Expected two symbols (CE and PE) from backend.");
				return;
			}

			const ceSymbol = symbols[0];
			const peSymbol = symbols[1];

			document.getElementById("chart-title-CE").textContent = `${ceSymbol}`;
			setupChart("chart-CE", ceSymbol, {
				high: "buy-btn-CE",
				mktbuy: "mkt-btn-CE",
				reset: "sell-btn-CE",
			});

			document.getElementById("chart-title-PE").textContent = `${peSymbol}`;
			setupChart("chart-PE", peSymbol, {
				high: "buy-btn-PE",
				mktbuy: "mkt-btn-PE",
				reset: "sell-btn-PE",
			});
		} catch (error) {
			console.error("Error initializing charts:", error);
		}
	}

	initCharts();
});
