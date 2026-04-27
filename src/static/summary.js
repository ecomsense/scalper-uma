console.log("summary.js v11 - starting");

let cachedOrders = [];
let cachedPositions = [];
let cachedM2M = 0;
let cachedRealized = 0;

function doFetch() {
    fetch("/api/summary")
        .then(r => r.json())
        .then(data => {
            // Save to localStorage
            localStorage.setItem("orders_cache", JSON.stringify(data.orders || []));
            localStorage.setItem("positions_cache", JSON.stringify(data.positions || []));

            // Update global vars
            cachedOrders = data.orders || [];
            cachedPositions = data.positions || [];
            cachedM2M = data.m2m || 0;
            cachedRealized = data.realized_pnl || 0;

            // Update bottom panel
            const posEl = document.getElementById("pos-count");
            const ordEl = document.getElementById("order-count");
            const m2mEl = document.getElementById("m2m");
            const realEl = document.getElementById("realized");
            const m2mElFooter = document.getElementById("m2m-footer");
            const realElFooter = document.getElementById("realized-footer");

            const orderCount = data.order_count || 0;
            const positionCount = data.position_count || 0;
            const activeOrders = data.active_orders || 0;

            if (posEl) posEl.textContent = positionCount;
            if (document.getElementById('pos-count-footer')) document.getElementById('pos-count-footer').textContent = positionCount;
            if (ordEl) ordEl.textContent = activeOrders + ' / ' + orderCount;
            if (document.getElementById('order-count-footer')) document.getElementById('order-count-footer').textContent = activeOrders + ' / ' + orderCount;
            if (m2mEl) {
                m2mEl.textContent = (data.m2m || 0).toFixed(2);
                m2mEl.parentElement.classList.toggle("negative", data.m2m < 0);
            }
            if (m2mElFooter) {
                m2mElFooter.textContent = (data.m2m || 0).toFixed(2);
                m2mElFooter.parentElement.classList.toggle("negative", data.m2m < 0);
            }
            if (realEl) {
                realEl.textContent = (data.realized_pnl || 0).toFixed(2);
                realEl.parentElement.classList.toggle("negative", data.realized_pnl < 0);
            }
            if (realElFooter) {
                realElFooter.textContent = (data.realized_pnl || 0).toFixed(2);
                realElFooter.parentElement.classList.toggle("negative", data.realized_pnl < 0);
            }
        })
        .catch(e => console.error("summary API error:", e));
}

window.fetchSummaryCache = function() { doFetch(); };

// Auto-fetch on page load
window.addEventListener("DOMContentLoaded", function() {
    console.log("summary.js v11 - page loaded, starting polls");
    doFetch();
    setInterval(doFetch, 5000);
});

// Show from localStorage (not from API)
function showPositionsModal() {
    const positions = cachedPositions.length > 0 ? cachedPositions : JSON.parse(localStorage.getItem("positions_cache") || "[]");
    if (positions.length === 0) {
        alert("No positions cached. Please wait for data to load.");
        return;
    }

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

// Show from localStorage (not from API)
function showOrdersModal() {
    const orders = cachedOrders.length > 0 ? cachedOrders : JSON.parse(localStorage.getItem("orders_cache") || "[]");
    if (orders.length === 0) {
        alert("No orders cached. Please wait for data to load.");
        return;
    }

    let html = '<table style="width:100%;border-collapse:collapse;">';
    html += '<tr><th style="border:1px solid #ddd;padding:8px;">Time</th><th style="border:1px solid #ddd;padding:8px;">OrderId</th><th style="border:1px solid #ddd;padding:8px;">Symbol</th><th style="border:1px solid #ddd;padding:8px;">Side</th><th style="border:1px solid #ddd;padding:8px;">Status</th><th style="border:1px solid #ddd;padding:8px;">Price</th></tr>';
    orders.forEach(function(o) {
        const status = o.status || '';
        let bg = '';
        // Only show green badge for OPEN or TRIGGER_PENDING
        if (status === 'OPEN' || status === 'TRIGGER_PENDING') bg = 'background:#44cc44;color:white;border-radius:8px;padding:4px 8px;';
        else if (status === 'CANCELED' || status === 'REJECTED') bg = 'background:#ff4444;color:white;border-radius:8px;padding:4px 8px;';
        // Extract time - if timestamp has space, take second part, otherwise show as-is
        const ts = o.broker_timestamp || '';
        const time = ts.includes(' ') ? ts.split(' ')[1] : (ts.includes('T') ? ts.split('T')[1] : ts);
        html += '<tr>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + time + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.order_id || '') + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.cname || '') + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.side || '') + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;' + bg + '">' + status + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.price || '') + '</td>';
        html += '</tr>';
    });
    });
    html += '</table>';
    document.getElementById("ordersTable").innerHTML = html;
    document.getElementById("ordersModal").style.display = "block";
}

console.log("summary.js v11 - ready");