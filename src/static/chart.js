window.addEventListener("DOMContentLoaded", () => {
  const chartContainer = document.getElementById("chartContainer");
  const symbolSelect = document.getElementById("symbolSelect");
  const buyButton = document.getElementById("buyButton");
  const sellButton = document.getElementById("sellButton");
  const symbolHeading = document.querySelector(".controls h4");

  let candleEventSource = null;
  let orderEventSource = null;
  let currentSymbol = null;

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

  const buyLineSeries = chart.addSeries(LightweightCharts.LineSeries, {
    color: "#00FF00",
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Solid,
    crosshairMarkerVisible: false,
    lastValueVisible: false,
    priceLineVisible: false,
  });

  const sellLineSeries = chart.addSeries(LightweightCharts.LineSeries, {
    color: "#FF0000",
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    crosshairMarkerVisible: false,
    lastValueVisible: false,
    priceLineVisible: false,
  });

  let currentSymbolOrders = {
    buy: [],
    sell: [],
  };

  function updateOrderLines() {
    buyLineSeries.setData(currentSymbolOrders.buy);
    sellLineSeries.setData(currentSymbolOrders.sell);
  }

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

    orderEventSource.addEventListener("order_update", (event) => {
      const allOrders = JSON.parse(event.data);
      const buyLines = [];
      const stopLines = [];

      for (const order of allOrders) {
        console.log(order);
        if (order.symbol !== currentSymbol) continue;

        const line = {
          time: Math.floor(new Date(order.exchange_timestamp).getTime() / 1000), // seconds
          value: parseFloat(order.price),
        };

        if (order.side === "BUY") {
          buyLines.push(line);
        } else if (order.side === "SELL") {
          stopLines.push(line);
        }
      }

      currentSymbolOrders.buy = buyLines;
      currentSymbolOrders.sell = stopLines;
      updateOrderLines();
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
  }

  symbolSelect.addEventListener("change", (event) => {
    const selectedSymbol = event.target.value;
    candlestickSeries.setData([]);
    currentSymbolOrders.buy = [];
    currentSymbolOrders.sell = [];
    updateOrderLines();
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
  connectOrderSSE();

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
