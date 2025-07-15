window.addEventListener("DOMContentLoaded", () => {
  const chartContainer = document.getElementById("chartContainer");
  const symbolSelect = document.getElementById("symbolSelect");
  const buyButton = document.getElementById("buyButton");
  const sellButton = document.getElementById("sellButton");
  const symbolHeading = document.querySelector(".controls h4");

  let candleEventSource = null;
  let orderEventSource = null;
  let currentSymbol = null;
  let renderedOrderIds = new Set();

  const orderSeriesMap = new Map(); // order_id → LineSeries

  const chart = LightweightCharts.createChart(chartContainer, {
    width: chartContainer.clientWidth,
    height: chartContainer.clientHeight,
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
  });

  const candlestickSeries = chart.addSeries(
    LightweightCharts.CandlestickSeries,
    {
      upColor: "#4CAF50",
      downColor: "#f44336",
      borderVisible: false,
      wickUpColor: "#4CAF50",
      wickDownColor: "#f44336",
    },
  );

  function connectCandleSSE(symbol) {
    if (candleEventSource) candleEventSource.close();

    currentSymbol = symbol;
    symbolHeading.textContent = symbol;
    candleEventSource = new EventSource(`/sse/candlesticks/${symbol}`);

    candleEventSource.addEventListener("initial_data", (event) => {
      const data = JSON.parse(event.data);
      candlestickSeries.setData(data);
      chart.timeScale().fitContent();
    });

    candleEventSource.addEventListener("live_update", (event) => {
      const data = JSON.parse(event.data);
      candlestickSeries.update(data);
    });

    candleEventSource.onerror = (error) => {
      console.error(`Candlestick SSE error for ${symbol}:`, error);
    };
  }

  function connectOrderSSE() {
    if (orderEventSource) orderEventSource.close();

    orderEventSource = new EventSource(`/sse/orders`);
    renderedOrderIds = new Set();

    orderEventSource.addEventListener("order_update", (event) => {
      const allOrders = JSON.parse(event.data);
      const bars = candlestickSeries.data();
      if (bars.length < 2) return;

      const firstTime = bars[0].time;
      const lastTime = bars[bars.length - 1].time;

      for (const order of allOrders) {
        if (!order.symbol || order.symbol !== currentSymbol) continue;
        if (!order?.order_id || renderedOrderIds.has(order.order_id)) continue;
        if (!order?.exchange_timestamp || !order?.price || !order?.side) continue;
        if (["CANCELED", "COMPLETE", "REJECTED"].includes(order.status)) continue;
        if (isNaN(parseFloat(price))) continue;

        const segment = [
          { time: firstTime, value: price },
          { time: lastTime, value: price },
        ];

        const series = chart.addSeries(LightweightCharts.LineSeries, {
          color: order.side === "B" ? "#00FF00" : "#FF0000",
          lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Solid,
          crosshairMarkerVisible: false,
          lastValueVisible: false,
          priceLineVisible: false,
        });

        series.setData(segment);
        orderSeriesMap.set(order.order_id, series);
        renderedOrderIds.add(order.order_id);
      }
    });

    orderEventSource.onerror = (err) => {
      console.error("Order SSE error:", err);
    };
  }

  async function populateSymbols() {
    let symbols = [];

    try {
      const response = await fetch("/api/symbols");
      const data = await response.json();
      if (Array.isArray(data) && data.length > 0) {
        symbols = data;
      }
    } catch (error) {
      console.error("Error loading symbols:", error);
    }

    if (symbols.length === 0) {
      symbols = ["DUMMY"];
    }

    symbolSelect.innerHTML = "";
    for (const symbol of symbols) {
      const option = document.createElement("option");
      option.value = symbol;
      option.textContent = symbol;
      symbolSelect.appendChild(option);
    }

    const defaultSymbol = symbols[0];
    symbolSelect.value = defaultSymbol;
    connectCandleSSE(defaultSymbol);
    connectOrderSSE();
  }

  symbolSelect.addEventListener("change", (event) => {
    const selectedSymbol = event.target.value;
    currentSymbol = selectedSymbol;

    // Clear chart
    candlestickSeries.setData([]);
    renderedOrderIds.clear();

    // Remove all previous LineSeries (one per order)
    for (const series of orderSeriesMap.values()) {
      chart.removeSeries(series);
    }
    orderSeriesMap.clear();

    connectCandleSSE(selectedSymbol);
  });

  buyButton.addEventListener("click", async () => {
    if (!currentSymbol) return alert("Select a symbol first.");
    const candles = candlestickSeries.data();
    if (candles.length < 2) return alert("Not enough candle data.");

    const prevCandle = candles[candles.length - 2];
    const payload = {
      symbol: currentSymbol,
      high: prevCandle.high,
      low: prevCandle.low,
    };

    try {
      const response = await fetch("/api/trade/buy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (result.status !== "success") {
        chart.timeScale().fitContent();
        alert("Buy order failed.");
      }
    } catch (error) {
      console.error("Buy order failed:", error);
      alert("Buy order failed.");
    }
  });

  sellButton.addEventListener("click", async () => {
    try {
      const response = await fetch("/api/trade/sell");
      const result = await response.json();
      if (result.status !== "success") {
        chart.timeScale().fitContent();
        alert("Sell order failed.");
      }
    } catch (error) {
      console.error("Sell order failed:", error);
      alert("Sell order failed.");
    }
  });

  // Init
  populateSymbols();

  // Resize observer
  new ResizeObserver((entries) => {
    if (entries.length === 0) return;
    const rect = entries[0].contentRect;
    chart.applyOptions({
      width: rect.width,
      height: rect.height,
    });
  }).observe(chartContainer);
});
