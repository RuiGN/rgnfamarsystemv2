(function () {
    'use strict';
    var target = document.getElementById('dashboard-main-chart');
    var empty = document.getElementById('dashboard-chart-empty');
    var payload = document.getElementById('dashboard-chart-data');
    if (!target || !payload || !window.ApexCharts) return;
    var data = JSON.parse(payload.textContent || '{}');
    if (!data.labels || !data.labels.length || !(data.series || []).some(function (value) { return Number(value) > 0; })) {
        target.hidden = true;
        if (empty) empty.hidden = false;
        return;
    }
    new window.ApexCharts(target, { chart: { type: 'bar', height: 300, toolbar: { show: false }, fontFamily: 'Inter, sans-serif' }, series: [{ name: 'Registros', data: data.series }], xaxis: { categories: data.labels, labels: { style: { fontSize: '11px' } } }, colors: ['#3454d1'], plotOptions: { bar: { borderRadius: 5, columnWidth: '42%' } }, dataLabels: { enabled: false }, grid: { borderColor: '#eef0f3' }, tooltip: { y: { formatter: function (value) { return String(value); } } }, responsive: [{ breakpoint: 768, options: { chart: { height: 240 }, xaxis: { labels: { rotate: -35 } } } }] }).render();
}());
