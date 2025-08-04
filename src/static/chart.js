window.addEventListener("DOMContentLoaded", () => {
  const chartContainer = document.getElementById("chartContainer");
  const buyButton = document.getElementById("buyButton");
  const symbolSelect = document.getElementById("symbolSelect");
  const mktButton = document.getElementById("mktButton");
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
        const price = parseFloat(order.price)
        if (isNaN(price)) continue;
        console.log(order)
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

  function resetOrderLines() {
    renderedOrderIds.clear();

    for (const series of orderSeriesMap.values()) {
      chart.removeSeries(series);
    }

    orderSeriesMap.clear();
  }

  buyButton.addEventListener("click", async () => {
    if (!currentSymbol) return alert("Select a symbol first.");
    const candles = candlestickSeries.data();
    if (candles.length < 2) return alert("Not enough candle data.");
    
    resetOrderLines()
    const prevCandle = candles[candles.length - 2];
    const payload = {
      symbol: currentSymbol,
      price: prevCandle.high + 0.05,
      trigger_price: prevCandle.high,
      order_type: "SL",
      exit_price: prevCandle.low,
    };

    try {
      resetOrderLines()
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
    // added on 17-jul 
    connectCandleSSE(currentSymbol);
  });


  symbolSelect.addEventListener("change", (event) => {
    const selectedSymbol = event.target.value;
    currentSymbol = selectedSymbol;
    // Clear chart
    candlestickSeries.setData([]);
    resetOrderLines()
    connectCandleSSE(selectedSymbol);
  });

  mktButton.addEventListener("click", async () => {
    if (!currentSymbol) return alert("Select a symbol first.");
    const candles = candlestickSeries.data();
    if (candles.length < 2) return alert("Not enough candle data.");
    
    resetOrderLines()
    const currCandle = candles[candles.length - 1];
    const payload = {
      symbol: currentSymbol,
      price: currCandle.close + 2,
      order_type: "LIMIT",
      exit_price: currCandle.low,
    };

    try {
      resetOrderLines()
      const response = await fetch("/api/trade/buy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (result.status !== "success") {
        chart.timeScale().fitContent();
        alert("Mkt order failed.");
      }
    } catch (error) {
      console.error("Mkt order failed:", error);
      alert("Mt order failed.");
    }
    connectCandleSSE(currentSymbol);
  });

  sellButton.addEventListener("click", async () => {
    try {
      resetOrderLines()
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
    // added on 17-jul 
    connectCandleSSE(currentSymbol);
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
