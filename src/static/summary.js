console.log('summary.js v11 - starting');

let cachedOrders = [];
let cachedPositions = [];
let cachedM2M = 0;
let cachedRealized = 0;

function doFetch() {
    fetch('/api/summary')
        .then(r => r.json())
        .then(data => {
            localStorage.setItem('orders_cache', JSON.stringify(data.orders || []));
            localStorage.setItem('positions_cache', JSON.stringify(data.positions || []));

            cachedOrders = data.orders || [];
            cachedPositions = data.positions || [];
            cachedM2M = data.m2m || 0;
            cachedRealized = data.realized_pnl || 0;

            const posEl = document.getElementById('pos-count');
            const ordEl = document.getElementById('order-count');
            const m2mEl = document.getElementById('m2m');
            const realEl = document.getElementById('realized');
            const m2mElFooter = document.getElementById('m2m-footer');
            const realElFooter = document.getElementById('realized-footer');

            const orderCount = data.order_count || 0;
            const positionCount = data.position_count || 0;
            const activeOrders = data.active_orders || 0;

            if (posEl) posEl.textContent = positionCount;
            if (document.getElementById('pos-count-footer')) document.getElementById('pos-count-footer').textContent = positionCount;
            if (ordEl) ordEl.textContent = activeOrders + ' / ' + orderCount;
            if (document.getElementById('order-count-footer')) document.getElementById('order-count-footer').textContent = activeOrders + ' / ' + orderCount;
            if (m2mEl) {
                m2mEl.textContent = (data.m2m || 0).toFixed(2);
                m2mEl.parentElement.classList.toggle('negative', data.m2m < 0);
            }
            if (m2mElFooter) {
                m2mElFooter.textContent = (data.m2m || 0).toFixed(2);
                document.getElementById('m2m-panel').classList.toggle('negative', data.m2m < 0);
            }
            if (realEl) {
                realEl.textContent = (data.realized_pnl || 0).toFixed(2);
                realEl.parentElement.classList.toggle('negative', data.realized_pnl < 0);
            }
            if (realElFooter) {
                realElFooter.textContent = (data.realized_pnl || 0).toFixed(2);
                document.getElementById('realized-panel').classList.toggle('negative', data.realized_pnl < 0);
            }
        })
        .catch(e => console.error('summary API error:', e));
}

window.fetchSummaryCache = function() { doFetch(); };

window.addEventListener('DOMContentLoaded', function() {
    console.log('summary.js v11 - page loaded, starting polls');
    doFetch();
    setInterval(doFetch, 5000);
});

function showPositionsModal() {
    const positions = cachedPositions.length > 0 ? cachedPositions : JSON.parse(localStorage.getItem('positions_cache') || '[]');
    if (positions.length === 0) {
        alert('No positions cached. Please wait for data to load.');
        return;
    }

    let html = '<table style="width:100%;border-collapse:collapse;">';
    html += '<tr><th style="border:1px solid #ddd;padding:8px;">Symbol</th><th style="border:1px solid #ddd;padding:8px;">LTP</th><th style="border:1px solid #ddd;padding:8px;">Qty</th><th style="border:1px solid #ddd;padding:8px;">RPNL</th><th style="border:1px solid #ddd;padding:8px;">M2M</th><th style="border:1px solid #ddd;padding:8px;">Action</th></tr>';
    positions.forEach(function(p) {
        const qty = p.quantity || 0;
        const ltp = p.last_price || 0;
        const symbol = p.symbol || '';
        const actionBtn = qty > 0 
            ? '<button style="background:#e67e22;color:white;border:none;padding:4px 8px;border-radius:4px;cursor:pointer" onclick="squareOff(\'' + symbol + '\')">Square</button>'
            : '<button style="background:#2d8a2d;color:white;border:none;padding:4px 8px;border-radius:4px;cursor:pointer" onclick="addPosition(\'' + symbol + '\',' + ltp + ',' + (p.ls || 65) + ')">Add</button>';
        const rowColor = qty > 0 ? 'color:#e67e22;' : (qty < 0 ? 'color:#2d8a2d;' : '');
        html += '<tr style="' + rowColor + '">';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (p.cname || p.symbol || '') + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + ltp.toFixed(2) + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + qty + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (p.rpnl || 0) + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (p.urmtom || 0) + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + actionBtn + '</td>';
        html += '</tr>';
    });
    html += '</table>';
    document.getElementById('positionsTable').innerHTML = html;
    document.getElementById('positionsModal').style.display = 'block';
}

function showOrdersModal() {
    const orders = cachedOrders.length > 0 ? cachedOrders : JSON.parse(localStorage.getItem('orders_cache') || '[]');
    if (orders.length === 0) {
        alert('No orders cached. Please wait for data to load.');
        return;
    }

    let html = '<table style="width:100%;border-collapse:collapse;">';
    html += '<tr><th style="border:1px solid #ddd;padding:8px;">Time</th><th style="border:1px solid #ddd;padding:8px;">OrderId</th><th style="border:1px solid #ddd;padding:8px;">Symbol</th><th style="border:1px solid #ddd;padding:8px;">Side</th><th style="border:1px solid #ddd;padding:8px;">Status</th><th style="border:1px solid #ddd;padding:8px;">Price</th></tr>';
    orders.forEach(function(o) {
        const status = (o.status || '').trim().toUpperCase();
        let statusBg = '';
        if (status === 'OPEN' || status === 'TRIGGER_PENDING') statusBg = 'background:#2d8a2d;color:white;border-radius:8px;padding:4px 8px;';
        else if (status === 'COMPLETE') statusBg = 'background:#6c757d;color:white;border-radius:8px;padding:4px 8px;';
        else if (status === 'CANCELED') statusBg = 'background:#c9a227;color:white;border-radius:8px;padding:4px 8px;';
        else if (status === 'REJECTED') statusBg = 'background:#e67e22;color:white;border-radius:8px;padding:4px 8px;';
        else statusBg = 'background:#666;color:white;border-radius:8px;padding:4px 8px;';
        const side = (o.side || '').trim().toUpperCase();
        let rowColor = side === 'B' ? '#1e7a1e' : (side === 'S' ? '#a93226' : '');
        const ts = o.broker_timestamp || '';
        let time = '';
        if (ts) {
            const parts = ts.split(' ');
            if (parts.length >= 1 && parts[0].includes(':')) {
                time = parts[0];
            } else {
                time = ts;
            }
        }
        html += '<tr style="color:' + rowColor + '">';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + time + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.order_id || '') + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.cname || '') + '</td>';
        let sideBg = side === 'B' ? 'background:#2d8a2d;color:white;border-radius:8px;padding:4px 8px;' : (side === 'S' ? 'background:#c0392b;color:white;border-radius:8px;padding:4px 8px;' : '');
        html += '<td style="border:1px solid #ddd;padding:4px;' + sideBg + '">' + (o.side || '') + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;' + statusBg + '">' + status + '</td>';
        html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.price || '') + '</td>';
        html += '</tr>';
    });
    html += '</table>';
    document.getElementById('ordersTable').innerHTML = html;
    document.getElementById('ordersModal').style.display = 'block';
}

function squareOff(symbol) {
    console.log('Square off:', symbol);
    alert('Square off for ' + symbol + ' - feature coming soon');
}

function addPosition(symbol, ltp, quantity) {
    console.log('Add position:', symbol, 'LTP:', ltp);
    document.getElementById('buySymbol').textContent = symbol;
    document.getElementById('buyLtp').textContent = ltp.toFixed(2);
    document.getElementById('buyPrice').value = ltp.toFixed(2);
    document.getElementById('buyExitPrice').value = (ltp * 0.95).toFixed(2);
    document.getElementById('buyCostPrice').value = ltp.toFixed(2);
    document.getElementById('buyQty').value = quantity || 65;
    document.getElementById('buyOrderModal').style.display = 'block';
}

function closeBuyOrderModal() {
    document.getElementById('buyOrderModal').style.display = 'none';
}

function submitBuyOrder() {
    const symbol = document.getElementById('buySymbol').textContent;
    const price = parseFloat(document.getElementById('buyPrice').value);
    const quantity = parseInt(document.getElementById('buyQty').value);

    fetch('/api/position/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            symbol: symbol,
            quantity: quantity,
            price: price,
            order_type: 'LIMIT'
        })
    }).then(r => r.json()).then(d => {
        alert(d.message || 'Order placed');
        closeBuyOrderModal();
    }).catch(e => {
        alert('Error: ' + e);
    });
}

console.log('summary.js v12 - ready');