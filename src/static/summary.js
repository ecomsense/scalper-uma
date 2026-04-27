console.log("summary.js v10 - starting");

function doFetch() {
    console.log("Fetching /api/summary...");
    fetch("/api/summary")
        .then(r => r.json())
        .then(data => {
            console.log("summary API success:", data);
            localStorage.setItem("summary_cache", JSON.stringify(data));
            updateFromCache();
        })
        .catch(e => console.error("API error:", e));
}

// Auto-fetch on page load
window.addEventListener("DOMContentLoaded", function() {
    console.log("Page loaded, fetching summary...");
    doFetch();
    // Refresh every 5 seconds for live M2M/realized updates
    setInterval(doFetch, 5000);
});

function updateFromCache() {
    const cached = localStorage.getItem("summary_cache");
    if (!cached) return;
    let data;
    try { data = JSON.parse(cached); } catch (e) { return; }
    
    const orderCount = data.order_count || 0;
    const positionCount = data.position_count || 0;
    const realizedPnl = data.realized_pnl || 0;
    if (orderCount === 0 && positionCount === 0 && realizedPnl === 0) return;

    const posEl = document.getElementById("pos-count");
    const ordEl = document.getElementById("order-count");
    const m2mEl = document.getElementById("m2m");
    const realEl = document.getElementById("realized");
    if (posEl) posEl.textContent = positionCount;
    if (ordEl) ordEl.textContent = (data.active_orders || 0) + "/" + orderCount;
    if (m2mEl) {
        m2mEl.textContent = (data.m2m || 0).toFixed(2);
        m2mEl.parentElement.classList.toggle("negative", data.m2m < 0);
    }
    if (realEl) {
        realEl.textContent = realizedPnl.toFixed(2);
        realEl.parentElement.classList.toggle("negative", realizedPnl < 0);
    }
}

window.fetchSummaryCache = function() { doFetch(); };

async function showPositionsModal() {
    let data = null;
    let cached = localStorage.getItem("summary_cache");
    if (cached) {
        try { data = JSON.parse(cached); } catch (e) {}
    }
    if (!data) {
        console.log("No cached data, fetching...");
        await new Promise(function(resolve) {
            fetch("/api/summary")
                .then(r => r.json())
                .then(function(d) {
                    localStorage.setItem("summary_cache", JSON.stringify(d));
                    data = d;
                    resolve();
                })
                .catch(function(e) { console.error(e); resolve(); });
        });
        if (!data) return;
    }
    const positions = data.positions || [];
    let html = '<table style="width:100%;border-collapse:collapse;">';
    html += '<tr><th style="border:1px solid #ddd;padding:8px;">Symbol</th><th style="border:1px solid #ddd;padding:8px;">Qty</th><th style="border:1px solid #ddd;padding:8px;">RPNL</th><th style="border:1px solid #ddd;padding:8px;">M2M</th></tr>';
    positions.forEach(function(p) {
        html += '<tr>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (p.cname || p.symbol || '') + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (p.quantity || 0) + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (p.rpnl || 0) + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (p.urmtom || 0) + '</td>';
        html += '</tr>';
    });
    html += '</table>';
    document.getElementById("positionsTable").innerHTML = html;
    document.getElementById("positionsModal").style.display = "block";
}

async function showOrdersModal() {
    let data = null;
    let cached = localStorage.getItem("summary_cache");
    if (cached) {
        try { data = JSON.parse(cached); } catch (e) {}
    }
    if (!data) {
        console.log("No cached data, fetching...");
        await new Promise(function(resolve) {
            fetch("/api/summary")
                .then(r => r.json())
                .then(function(d) {
                    localStorage.setItem("summary_cache", JSON.stringify(d));
                    data = d;
                    resolve();
                })
                .catch(function(e) { console.error(e); resolve(); });
        });
        if (!data) return;
    }
    const orders = data.orders || [];
    let html = '<table style="width:100%;border-collapse:collapse;">';
    html += '<tr><th style="border:1px solid #ddd;padding:8px;">Time</th><th style="border:1px solid #ddd;padding:8px;">Symbol</th><th style="border:1px solid #ddd;padding:8px;">OrderID</th><th style="border:1px solid #ddd;padding:8px;">Side</th><th style="border:1px solid #ddd;padding:8px;">Status</th><th style="border:1px solid #ddd;padding:8px;">Price</th></tr>';
    orders.forEach(function(o) {
        const status = o.status || '';
        let bg = '';
        if (status === 'COMPLETE') bg = 'background:#44cc44;color:white;border-radius:8px;padding:4px 8px;';
        else if (status === 'CANCELED' || status === 'REJECTED') bg = 'background:#ff4444;color:white;border-radius:8px;padding:4px 8px;';
        html += '<tr>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.broker_timestamp || '') + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.tsym || '') + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.order_id || '') + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.side || '') + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;' + bg + '">' + status + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.price || '') + '</td>';
        html += '</tr>';
    });
    html += '</table>';
    document.getElementById("ordersTable").innerHTML = html;
    document.getElementById("ordersModal").style.display = "block";
}

console.log("summary.js v8 - ready");