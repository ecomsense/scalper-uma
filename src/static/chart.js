window.addEventListener("DOMContentLoaded", () => {
	let orderEventSource = null;
	const orderSeriesMap = new Map();

	const chartOptions = {
		// width: 500,
		// height: 300,
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

		function setupChart(containerId, symbol, buttonIds) {
		const chartContainer = document.getElementById(containerId);
		if (!chartContainer) {
			console.error(`Chart container with ID '${containerId}' not found.`);
			return;
		}

		const chart = LightweightCharts.createChart(chartContainer, chartOptions);
		const candlestickSeries = chart.addSeries(
			LightweightCharts.CandlestickSeries,
			candlestickOptions,
		);

		const maSeries = chart.addSeries(LightweightCharts.LineSeries, {
			color: "#FFA500",
			lineWidth: 2,
		});

		// --- THIS IS THE FIX ---
		chart.timeScale().applyOptions({
			timeZone: "Asia/Kolkata",
		});

		let candleData = [];

		function calculateMA(data, period = 9) {
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

		function updateMA() {
			if (candleData.length >= 9) {
				const maData = calculateMA(candleData, 9);
				maSeries.setData(maData);
			}
		}

		const candleEventSource = new EventSource(`/sse/candlesticks/${symbol}`);

		candleEventSource.addEventListener("initial_data", (event) => {
			const data = JSON.parse(event.data);
			if (data.length > 0) {
				candleData = data;
				candlestickSeries.setData(data);
				updateMA();
				chart.timeScale().fitContent();
			}
		});

		candleEventSource.addEventListener("live_update", (event) => {
			const data = JSON.parse(event.data);
			candlestickSeries.update(data);
			candleData.push(data);
			updateMA();
		});

		candleEventSource.onerror = (error) => {
			console.error(`Candlestick SSE error for ${symbol}:`, error);
			candleEventSource.close();
		};

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
		/*
        new ResizeObserver((entries) => {
            if (entries.length === 0) return;
            const rect = entries[0].contentRect;
            chart.applyOptions({
                width: rect.width,
                height: rect.height,
            });
        }).observe(chartContainer);
        */
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
