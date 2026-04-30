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

    let html = '<table class="modal-table"><tr class="modal-tr"><th class="modal-th">Symbol</th><th class="modal-th">Exchange</th><th class="modal-th">LTP</th><th class="modal-th">Qty</th><th class="modal-th">RPNL</th><th class="modal-th">M2M</th><th class="modal-th">Action</th></tr>';
    positions.forEach(function(p) {
        const qty = p.quantity || 0;
        const ltp = p.last_price || 0;
        const symbol = p.symbol || '';
        const exchange = p.exchange || 'NFO';
        let actionBtn = '';
        if (qty > 0) {
            actionBtn = '<button class="btn-action btn-square" onclick="squareOff(\'' + symbol + '\',' + qty + ',' + ltp + ',\'' + exchange + '\')">Square</button>';
        } else if (qty < 0) {
            actionBtn = '<button class="btn-action btn-cover" onclick="coverPosition(\'' + symbol + '\',' + Math.abs(qty) + ',' + ltp + ',\'' + exchange + '\')">Cover</button>';
        } else {
            actionBtn = '<button class="btn-action btn-add" onclick="addPosition(\'' + symbol + '\',' + ltp + ',' + (p.ls || 65) + ',\'' + exchange + '\')">Add</button>';
        }
        const rowClass = qty > 0 ? 'row-sell' : (qty < 0 ? 'row-buy' : '');
        html += '<tr class="' + rowClass + '">';
        html += '<td class="modal-td">' + (p.cname || p.symbol || '') + '</td>';
        html += '<td class="modal-td">' + exchange + '</td>';
        html += '<td class="modal-td">' + ltp.toFixed(2) + '</td>';
        html += '<td class="modal-td">' + qty + '</td>';
        html += '<td class="modal-td">' + (p.rpnl || 0) + '</td>';
        html += '<td class="modal-td">' + (p.urmtom || 0) + '</td>';
        html += '<td class="modal-td">' + actionBtn + '</td>';
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

    let html = '<table class="modal-table"><tr class="modal-tr"><th class="modal-th">Time</th><th class="modal-th">OrderId</th><th class="modal-th">Symbol</th><th class="modal-th">Side</th><th class="modal-th">Status</th><th class="modal-th">Price</th></tr>';
    orders.forEach(function(o) {
        const status = (o.status || '').trim().toUpperCase();
        const orderId = o.order_id || '';
        let statusClass = 'status-other';
        let cancelBtn = '';
        if (status === 'OPEN' || status === 'TRIGGER_PENDING') {
            statusClass = 'status-open';
            cancelBtn = ' <button class="cancel-btn" onclick="cancelOrder(\'' + orderId + '\')">X</button>';
        }
        else if (status === 'COMPLETE') statusClass = 'status-complete';
        else if (status === 'CANCELED') statusClass = 'status-cancelled';
        else if (status === 'REJECTED') statusClass = 'status-rejected';
        const side = (o.side || '').trim().toUpperCase();
        const rowClass = side === 'B' ? 'row-buy' : (side === 'S' ? 'row-sell' : '');
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
        const sideClass = side === 'B' ? 'side-buy' : (side === 'S' ? 'side-sell' : '');
        html += '<tr class="' + rowClass + '">';
        html += '<td class="modal-td">' + time + '</td>';
        html += '<td class="modal-td">' + (o.order_id || '') + '</td>';
        html += '<td class="modal-td">' + (o.cname || '') + '</td>';
        html += '<td class="modal-td"><span class="side-badge ' + sideClass + '">' + (o.side || '') + '</span></td>';
        html += '<td class="modal-td"><span class="status-badge ' + statusClass + '">' + status + cancelBtn + '</span></td>';
        html += '<td class="modal-td">' + (o.price || '') + '</td>';
        html += '</tr>';
    });
    html += '</table>';
    document.getElementById('ordersTable').innerHTML = html;
    document.getElementById('ordersModal').style.display = 'block';
}

function squareOff(symbol, qty, ltp, exchange) {
    console.log('Square off (long):', symbol, 'qty:', qty, 'ltp:', ltp, 'price:', (ltp - 2));
    fetch('/api/position/square', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            symbol: symbol,
            quantity: qty,
            ltp: ltp,
            exchange: exchange
        })
    }).then(r => r.json()).then(d => {
        alert(d.message || 'Square order placed');
        closePositionsModal();
    }).catch(e => {
        alert('Error: ' + e);
    });
}

function coverPosition(symbol, qty, ltp, exchange) {
    console.log('Cover position (short):', symbol, 'qty:', qty, 'ltp:', ltp, 'price:', (ltp + 2));
    fetch('/api/position/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            symbol: symbol,
            quantity: qty,
            price: ltp + 2,
            order_type: 'LIMIT',
            trigger_price: 0,
            validity: 'DAY'
        })
    }).then(r => r.json()).then(d => {
        alert(d.message || 'Cover order placed');
        closePositionsModal();
    }).catch(e => {
        alert('Error: ' + e);
    });
}

function addPosition(symbol, ltp, quantity, exchange) {
    console.log('Add position:', symbol, 'LTP:', ltp, 'Exchange:', exchange);
    document.getElementById('buySymbol').textContent = symbol;
    document.getElementById('buyExchange').textContent = exchange || 'NFO';
    document.getElementById('buyPrice').value = ltp.toFixed(2);
    document.getElementById('buyQty').value = quantity || 65;
    document.getElementById('buyOrderModal').style.display = 'block';
}

function closeBuyOrderModal() {
    document.getElementById('buyOrderModal').style.display = 'none';
}

function submitBuyOrder() {
    const symbol = document.getElementById('buySymbol').textContent;
    const quantity = parseInt(document.getElementById('buyQty').value);
    const price = parseFloat(document.getElementById('buyPrice').value) || 0;

    fetch('/api/position/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            symbol: symbol,
            quantity: quantity,
            price: price,
            order_type: 'LIMIT',
            trigger_price: 0,
            validity: 'DAY'
        })
    }).then(r => r.json()).then(d => {
        alert(d.message || 'Order placed');
        closeBuyOrderModal();
    }).catch(e => {
        alert('Error: ' + e);
    });
}

function cancelOrder(orderId) {
    if (!confirm('Cancel order ' + orderId + '?')) return;
    fetch('/api/order/cancel', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({order_id: orderId})
    }).then(r => r.json()).then(d => {
        alert(d.message || 'Order cancelled');
        closeOrdersModal();
    }).catch(e => {
        alert('Error: ' + e);
    });
}

console.log('summary.js v12 - ready');