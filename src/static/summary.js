// Summary module - fetches and caches positions + orders from broker

window.fetchSummaryCache = function() {
    fetch("/api/summary")
        .then(r => r.json())
        .then(data => {
            localStorage.setItem("summary_cache", JSON.stringify(data));
        })
        .catch(console.error);
};

window.showPositionsModal = function() {
    const cached = localStorage.getItem("summary_cache");
    if (!cached) return;
    
    let data;
    try {
        data = JSON.parse(cached);
    } catch (e) {
        return;
    }
    
    const positions = data.positions || [];
    
    let html = '<table style="width:100%;border-collapse:collapse;">';
    html += '<tr><th style="border:1px solid #ddd;padding:8px;">Symbol</th><th style="border:1px solid #ddd;padding:8px;">Qty</th><th style="border:1px solid #ddd;padding:8px;">RPNL</th><th style="border:1px solid #ddd;padding:8px;">M2M</th></tr>';
    
    if (positions.length > 0) {
        positions.forEach(p => {
            const qty = p.quantity || 0;
            html += '<tr>';
            html += '<td style="border:1px solid #ddd;padding:8px;">' + (p.cname || p.symbol || '') + '</td>';
            html += '<td style="border:1px solid #ddd;padding:8px;">' + qty + '</td>';
            html += '<td style="border:1px solid #ddd;padding:8px;">' + (p.rpnl || 0) + '</td>';
            html += '<td style="border:1px solid #ddd;padding:8px;">' + (p.urmtom || 0) + '</td>';
            html += '</tr>';
        });
    } else {
        html += '<tr><td colspan="4" style="border:1px solid #ddd;padding:8px;text-align:center;">No positions</td></tr>';
    }
    html += '</table>';
    
    document.getElementById("positionsTable").innerHTML = html;
    document.getElementById("positionsModal").style.display = "block";
};

window.showOrdersModal = function() {
    const cached = localStorage.getItem("summary_cache");
    if (!cached) return;
    
    let data;
    try {
        data = JSON.parse(cached);
    } catch (e) {
        return;
    }
    
    const orders = data.orders || [];
    
    let html = '<table style="width:100%;border-collapse:collapse;">';
    html += '<tr><th style="border:1px solid #ddd;padding:8px;">Time</th><th style="border:1px solid #ddd;padding:8px;">Symbol</th><th style="border:1px solid #ddd;padding:8px;">OrderID</th><th style="border:1px solid #ddd;padding:8px;">Side</th><th style="border:1px solid #ddd;padding:8px;">Status</th><th style="border:1px solid #ddd;padding:8px;">Price</th></tr>';
    
    if (orders.length > 0) {
        orders.forEach(o => {
            const timeStr = o.broker_timestamp || '';
            const status = o.status || '';
            let statusBg = '';
            if (status === 'COMPLETE') {
                statusBg = 'background:#44cc44;color:white;border-radius:8px;padding:4px 8px;';
            } else if (status === 'CANCELED' || status === 'REJECTED') {
                statusBg = 'background:#ff4444;color:white;border-radius:8px;padding:4px 8px;';
            }
            
            html += '<tr>';
            html += '<td style="border:1px solid #ddd;padding:8px;">' + timeStr + '</td>';
            html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.tsym || o.symbol || '') + '</td>';
            html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.order_id || o.norenordno || '') + '</td>';
            html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.side || o.trantype || '') + '</td>';
            html += '<td style="border:1px solid #ddd;padding:8px;' + statusBg + '">' + status + '</td>';
            html += '<td style="border:1px solid #ddd;padding:8px;">' + (o.price || o.prc || '') + '</td>';
            html += '</tr>';
        });
    } else {
        html += '<tr><td colspan="6" style="border:1px solid #ddd;padding:8px;text-align:center;">No orders</td></tr>';
    }
    html += '</table>';
    
    document.getElementById("ordersTable").innerHTML = html;
    document.getElementById("ordersModal").style.display = "block";
};
