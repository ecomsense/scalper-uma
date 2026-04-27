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

    let html = '<table style=\u0022width:100%;border-collapse:collapse;\u0022>';
    html += '<tr><th style=\u0022border:1px solid #ddd;padding:8px;\u0022>Symbol</th><th style=\u0022border:1px solid #ddd;padding:8px;\u0022>Qty</th><th style=\u0022border:1px solid #ddd;padding:8px;\u0022>RPNL</th><th style=\u0022border:1px solid #ddd;padding:8px;\u0022>M2M</th></tr>';
    positions.forEach(function(p) {
        html += '<tr>';
        html += '<td style=\u0022border:1px solid #ddd;padding:8px;\u0022>' + (p.cname || p.symbol || '') + '</td>';
        html += '<td style=\u0022border:1px solid #ddd;padding:8px;\u0022>' + (p.quantity || 0) + '</td>';
        html += '<td style=\u0022border:1px solid #ddd;padding:8px;\u0022>' + (p.rpnl || 0) + '</td>';
        html += '<td style=\u0022border:1px solid #ddd;padding:8px;\u0022>' + (p.urmtom || 0) + '</td>';
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

    let html = '<table style=\u0022width:100%;border-collapse:collapse;\u0022>';
    html += '<tr><th style=\u0022border:1px solid #ddd;padding:8px;\u0022>Time</th><th style=\u0022border:1px solid #ddd;padding:8px;\u0022>OrderId</th><th style=\u0022border:1px solid #ddd;padding:8px;\u0022>Symbol</th><th style=\u0022border:1px solid #ddd;padding:8px;\u0022>Side</th><th style=\u0022border:1px solid #ddd;padding:8px;\u0022>Status</th><th style=\u0022border:1px solid #ddd;padding:8px;\u0022>Price</th></tr>';
    orders.forEach(function(o) {
        const status = o.status || '';
        let bg = '';
        if (status === 'OPEN' || status === 'TRIGGER_PENDING') bg = 'background:#44cc44;color:white;border-radius:8px;padding:4px 8px;';
        else if (status === 'CANCELED' || status === 'REJECTED') bg = 'background:#ff4444;color:white;border-radius:8px;padding:4px 8px;';
        const ts = o.broker_timestamp || '';
        const time = ts.includes(' ') ? ts.split(' ')[1] : (ts.includes('T') ? ts.split('T')[1] : ts);
        html += '<tr>';
        html += '<td style=\u0022border:1px solid #ddd;padding:8px;\u0022>' + time + '</td>';
        html += '<td style=\u0022border:1px solid #ddd;padding:8px;\u0022>' + (o.order_id || '') + '</td>';
        html += '<td style=\u0022border:1px solid #ddd;padding:8px;\u0022>' + (o.cname || '') + '</td>';
        html += '<td style=\u0022border:1px solid #ddd;padding:8px;\u0022>' + (o.side || '') + '</td>';
        html += '<td style=\u0022border:1px solid #ddd;padding:8px;' + bg + '\u0022>' + status + '</td>';
        html += '<td style=\u0022border:1px solid #ddd;padding:8px;\u0022>' + (o.price || '') + '</td>';
        html += '</tr>';
    });
    html += '</table>';
    document.getElementById('ordersTable').innerHTML = html;
    document.getElementById('ordersModal').style.display = 'block';
}

console.log('summary.js v11 - ready');